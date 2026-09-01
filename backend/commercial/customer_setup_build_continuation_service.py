"""
TODOBA Customer Setup Build Continuation Service

Owns one narrow, short-lived authority used only to continue an
already-authorized customer Setup package build after the original
setup handoff may have expired.

Security boundary:

    valid setup handoff
        -> accepted authoritative setup activation
        -> immutable deployment package build request
        -> build continuation issuance
        -> later build convergence / package delivery

The continuation credential does not grant permission to:
- create a customer
- create a setup activation
- select another account
- create another deployment
- register another package build request
- activate an unrelated deployment
- bypass deployment entitlement
- issue customer runtime access credentials

Credential format:

    tdbsc1.<continuation_id>.<secret>

Durable state stores only:
- issuance_request_id
- continuation_id
- setup_activation_id
- deployment_id
- account_fingerprint_sha256
- verifier_sha256
- issued_at
- expires_at
- status

Plaintext continuation credentials and plaintext account fingerprints
are never persisted.

Retry contract:
- the same setup activation + deployment derives the same issuance
  request identity
- retry keeps continuation_id, issued_at, and expires_at
- retry rotates the plaintext secret and verifier
- retry never extends lifetime
- expired or revoked continuations cannot be revived

Commercial identity remains authoritative elsewhere:
- CustomerSetupActivationStore owns customer/setup identity
- CustomerDeploymentPackageBuildRequestStore owns immutable build
  identity
- this owner never accepts customer_id from its caller
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from enum import Enum
import hashlib
from hmac import compare_digest
import json
import os
from pathlib import Path
import re
import secrets
import threading
import uuid

from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
)


STORE_VERSION = 1

_CONTINUATION_PREFIX = "tdbsc1"
_CONTINUATION_ID_RANDOM_BYTES = 16
_CONTINUATION_SECRET_RANDOM_BYTES = 32
_CONTINUATION_TTL = timedelta(hours=24)
_GENERATION_ATTEMPTS = 128

_CONTINUATION_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

_ISSUANCE_REQUEST_PREFIX = "setup-build-continuation-"


class CustomerSetupBuildContinuationStatus(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(
    frozen=True,
)
class CustomerSetupBuildContinuationRecord:
    issuance_request_id: str
    continuation_id: str
    setup_activation_id: str
    deployment_id: str
    account_fingerprint_sha256: str
    verifier_sha256: str
    issued_at: str
    expires_at: str
    status: CustomerSetupBuildContinuationStatus

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "issuance_request_id",
            "setup_activation_id",
            "deployment_id",
        ):
            object.__setattr__(
                self,
                name,
                _normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

        continuation_id = (
            _normalize_required_string(
                self.continuation_id,
                name="continuation_id",
            )
        )

        if not _CONTINUATION_ID_PATTERN.fullmatch(
            continuation_id
        ):
            raise ValueError(
                "continuation_id is invalid."
            )

        object.__setattr__(
            self,
            "continuation_id",
            continuation_id,
        )

        for name in (
            "account_fingerprint_sha256",
            "verifier_sha256",
        ):
            digest = (
                _normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                )
                .lower()
            )

            if not _SHA256_PATTERN.fullmatch(
                digest
            ):
                raise ValueError(
                    f"{name} must be a SHA-256 "
                    "hexadecimal digest."
                )

            object.__setattr__(
                self,
                name,
                digest,
            )

        object.__setattr__(
            self,
            "issued_at",
            _normalize_timestamp(
                self.issued_at,
                name="issued_at",
            ),
        )

        object.__setattr__(
            self,
            "expires_at",
            _normalize_timestamp(
                self.expires_at,
                name="expires_at",
            ),
        )

        if not isinstance(
            self.status,
            CustomerSetupBuildContinuationStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerSetupBuildContinuationStatus."
            )

        issued_at = _parse_timestamp(
            self.issued_at,
            name="issued_at",
        )

        expires_at = _parse_timestamp(
            self.expires_at,
            name="expires_at",
        )

        if expires_at <= issued_at:
            raise ValueError(
                "expires_at must be later than issued_at."
            )


@dataclass(
    frozen=True,
)
class CustomerSetupBuildContinuationIssuanceResult:
    issuance_request_id: str
    continuation_id: str
    setup_activation_id: str
    deployment_id: str
    issued_at: str
    expires_at: str
    continuation_credential: str = field(
        repr=False,
    )

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "issuance_request_id",
            "continuation_id",
            "setup_activation_id",
            "deployment_id",
            "issued_at",
            "expires_at",
            "continuation_credential",
        ):
            value = getattr(
                self,
                name,
            )

            if not isinstance(
                value,
                str,
            ):
                raise TypeError(
                    f"{name} must be str."
                )

            if (
                not value
                or value.strip() != value
            ):
                raise ValueError(
                    f"{name} is invalid."
                )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupBuildContinuationIssuanceResult("
            f"issuance_request_id="
            f"{self.issuance_request_id!r}, "
            f"continuation_id="
            f"{self.continuation_id!r}, "
            f"setup_activation_id="
            f"{self.setup_activation_id!r}, "
            f"deployment_id="
            f"{self.deployment_id!r}, "
            f"issued_at={self.issued_at!r}, "
            f"expires_at={self.expires_at!r}, "
            "continuation_credential=<redacted>)"
        )


@dataclass(
    frozen=True,
)
class CustomerSetupBuildContinuationAuthorization:
    continuation_id: str
    setup_activation_id: str
    customer_id: str
    deployment_id: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "continuation_id",
            "setup_activation_id",
            "customer_id",
            "deployment_id",
        ):
            object.__setattr__(
                self,
                name,
                _normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )


def derive_customer_setup_build_continuation_issuance_request_id(
    *,
    setup_activation_id: str,
    deployment_id: str,
) -> str:
    normalized_activation_id = (
        _normalize_required_string(
            setup_activation_id,
            name="setup_activation_id",
        )
    )

    normalized_deployment_id = (
        _normalize_required_string(
            deployment_id,
            name="deployment_id",
        )
    )

    digest = hashlib.sha256()

    digest.update(
        normalized_activation_id.encode(
            "utf-8"
        )
    )
    digest.update(
        b"\x00"
    )
    digest.update(
        normalized_deployment_id.encode(
            "utf-8"
        )
    )

    return (
        _ISSUANCE_REQUEST_PREFIX
        + digest.hexdigest()
    )


def derive_customer_setup_build_continuation_verifier(
    continuation_credential: str,
) -> str:
    normalized = _normalize_required_string(
        continuation_credential,
        name="continuation_credential",
    )

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


def derive_customer_setup_build_continuation_account_fingerprint(
    account_fingerprint: str,
) -> str:
    normalized = _normalize_required_string(
        account_fingerprint,
        name="account_fingerprint",
    )

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


class CustomerSetupBuildContinuationStore:
    """
    Durable mutable owner of build-continuation credential truth.

    The store never creates itself during ordinary construction.
    Existing durable state is reopened automatically.

    initialize_empty() is an explicit offline provisioning operation.
    """

    def __init__(
        self,
        storage_path: Path,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        self.storage_path = storage_path
        self._lock = threading.RLock()
        self._records: dict[
            str,
            CustomerSetupBuildContinuationRecord,
        ] = {}
        self._ready = False

        if self.storage_path.exists():
            self._records = (
                self._read_records()
            )
            self._ready = True

    @property
    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def initialize_empty(
        self,
    ) -> None:
        with self._lock:
            if self._ready:
                return

            if self.storage_path.exists():
                self._records = (
                    self._read_records()
                )
                self._ready = True
                return

            self.storage_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._write_records(
                {},
            )

            self._records = {}
            self._ready = True

    def all(
        self,
    ) -> tuple[
        CustomerSetupBuildContinuationRecord,
        ...,
    ]:
        with self._lock:
            self._require_ready()

            return tuple(
                sorted(
                    self._records.values(),
                    key=lambda record: (
                        record.continuation_id
                    ),
                )
            )

    def get(
        self,
        *,
        continuation_id: str,
    ) -> (
        CustomerSetupBuildContinuationRecord
        | None
    ):
        normalized = _normalize_required_string(
            continuation_id,
            name="continuation_id",
        )

        with self._lock:
            self._require_ready()

            return self._records.get(
                normalized
            )

    def get_by_issuance_request_id(
        self,
        *,
        issuance_request_id: str,
    ) -> (
        CustomerSetupBuildContinuationRecord
        | None
    ):
        normalized = _normalize_required_string(
            issuance_request_id,
            name="issuance_request_id",
        )

        with self._lock:
            self._require_ready()

            for record in (
                self._records.values()
            ):
                if (
                    record.issuance_request_id
                    == normalized
                ):
                    return record

            return None

    def get_by_verifier(
        self,
        *,
        verifier_sha256: str,
    ) -> (
        CustomerSetupBuildContinuationRecord
        | None
    ):
        normalized = _normalize_sha256(
            verifier_sha256,
            name="verifier_sha256",
        )

        with self._lock:
            self._require_ready()

            for record in (
                self._records.values()
            ):
                if (
                    record.verifier_sha256
                    == normalized
                ):
                    return record

            return None

    def get_active_by_setup_activation_id(
        self,
        *,
        setup_activation_id: str,
    ) -> (
        CustomerSetupBuildContinuationRecord
        | None
    ):
        normalized = _normalize_required_string(
            setup_activation_id,
            name="setup_activation_id",
        )

        with self._lock:
            self._require_ready()

            for record in (
                self._records.values()
            ):
                if (
                    record.setup_activation_id
                    == normalized
                    and record.status
                    is CustomerSetupBuildContinuationStatus.ACTIVE
                ):
                    return record

            return None

    def add(
        self,
        record: CustomerSetupBuildContinuationRecord,
    ) -> CustomerSetupBuildContinuationRecord:
        if not isinstance(
            record,
            CustomerSetupBuildContinuationRecord,
        ):
            raise TypeError(
                "record must be "
                "CustomerSetupBuildContinuationRecord."
            )

        with self._lock:
            self._require_ready()

            if (
                record.continuation_id
                in self._records
            ):
                raise ValueError(
                    "Duplicate build continuation_id."
                )

            if (
                self.get_by_issuance_request_id(
                    issuance_request_id=(
                        record.issuance_request_id
                    )
                )
                is not None
            ):
                raise ValueError(
                    "Duplicate build continuation "
                    "issuance request."
                )

            if (
                self.get_by_verifier(
                    verifier_sha256=(
                        record.verifier_sha256
                    )
                )
                is not None
            ):
                raise ValueError(
                    "Duplicate build continuation "
                    "verifier."
                )

            if (
                record.status
                is not
                CustomerSetupBuildContinuationStatus.ACTIVE
            ):
                raise ValueError(
                    "New build continuation must "
                    "start ACTIVE."
                )

            if (
                self.get_active_by_setup_activation_id(
                    setup_activation_id=(
                        record.setup_activation_id
                    )
                )
                is not None
            ):
                raise ValueError(
                    "Setup activation already has an "
                    "ACTIVE build continuation."
                )

            candidate = dict(
                self._records
            )

            candidate[
                record.continuation_id
            ] = record

            self._validate_records(
                candidate
            )
            self._write_records(
                candidate
            )

            self._records = candidate

            return record

    def rotate_verifier(
        self,
        *,
        continuation_id: str,
        verifier_sha256: str,
    ) -> CustomerSetupBuildContinuationRecord:
        normalized_id = _normalize_required_string(
            continuation_id,
            name="continuation_id",
        )

        normalized_verifier = (
            _normalize_sha256(
                verifier_sha256,
                name="verifier_sha256",
            )
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                normalized_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown build continuation."
                )

            if (
                existing.status
                is CustomerSetupBuildContinuationStatus.REVOKED
            ):
                raise ValueError(
                    "REVOKED build continuation "
                    "cannot rotate verifier."
                )

            verifier_owner = (
                self.get_by_verifier(
                    verifier_sha256=(
                        normalized_verifier
                    )
                )
            )

            if (
                verifier_owner is not None
                and verifier_owner.continuation_id
                != existing.continuation_id
            ):
                raise ValueError(
                    "Build continuation verifier "
                    "already belongs to another record."
                )

            updated = (
                CustomerSetupBuildContinuationRecord(
                    issuance_request_id=(
                        existing.issuance_request_id
                    ),
                    continuation_id=(
                        existing.continuation_id
                    ),
                    setup_activation_id=(
                        existing.setup_activation_id
                    ),
                    deployment_id=(
                        existing.deployment_id
                    ),
                    account_fingerprint_sha256=(
                        existing
                        .account_fingerprint_sha256
                    ),
                    verifier_sha256=(
                        normalized_verifier
                    ),
                    issued_at=(
                        existing.issued_at
                    ),
                    expires_at=(
                        existing.expires_at
                    ),
                    status=existing.status,
                )
            )

            candidate = dict(
                self._records
            )

            candidate[
                existing.continuation_id
            ] = updated

            self._validate_records(
                candidate
            )
            self._write_records(
                candidate
            )

            self._records = candidate

            return updated

    def revoke(
        self,
        *,
        continuation_id: str,
    ) -> CustomerSetupBuildContinuationRecord:
        normalized_id = _normalize_required_string(
            continuation_id,
            name="continuation_id",
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                normalized_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown build continuation."
                )

            if (
                existing.status
                is CustomerSetupBuildContinuationStatus.REVOKED
            ):
                return existing

            updated = (
                CustomerSetupBuildContinuationRecord(
                    issuance_request_id=(
                        existing.issuance_request_id
                    ),
                    continuation_id=(
                        existing.continuation_id
                    ),
                    setup_activation_id=(
                        existing.setup_activation_id
                    ),
                    deployment_id=(
                        existing.deployment_id
                    ),
                    account_fingerprint_sha256=(
                        existing
                        .account_fingerprint_sha256
                    ),
                    verifier_sha256=(
                        existing.verifier_sha256
                    ),
                    issued_at=(
                        existing.issued_at
                    ),
                    expires_at=(
                        existing.expires_at
                    ),
                    status=(
                        CustomerSetupBuildContinuationStatus
                        .REVOKED
                    ),
                )
            )

            candidate = dict(
                self._records
            )

            candidate[
                existing.continuation_id
            ] = updated

            self._validate_records(
                candidate
            )
            self._write_records(
                candidate
            )

            self._records = candidate

            return updated

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer setup build continuation "
                "store is not ready."
            )

    def _read_records(
        self,
    ) -> dict[
        str,
        CustomerSetupBuildContinuationRecord,
    ]:
        if not self.storage_path.is_file():
            raise RuntimeError(
                "Customer setup build continuation "
                "storage path is not a file."
            )

        try:
            payload = json.loads(
                self.storage_path.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise ValueError(
                "Customer setup build continuation "
                "store is invalid."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer setup build continuation "
                "store root must be an object."
            )

        if set(
            payload
        ) != {
            "version",
            "records",
        }:
            raise ValueError(
                "Customer setup build continuation "
                "store has invalid fields."
            )

        if (
            payload.get(
                "version"
            )
            != STORE_VERSION
        ):
            raise ValueError(
                "Unsupported customer setup build "
                "continuation store version."
            )

        items = payload.get(
            "records"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer setup build continuation "
                "records must be a list."
            )

        records: dict[
            str,
            CustomerSetupBuildContinuationRecord,
        ] = {}

        expected_fields = {
            "issuance_request_id",
            "continuation_id",
            "setup_activation_id",
            "deployment_id",
            "account_fingerprint_sha256",
            "verifier_sha256",
            "issued_at",
            "expires_at",
            "status",
        }

        for item in items:
            if (
                not isinstance(
                    item,
                    dict,
                )
                or set(
                    item
                )
                != expected_fields
            ):
                raise ValueError(
                    "Customer setup build continuation "
                    "item has invalid fields."
                )

            try:
                status = (
                    CustomerSetupBuildContinuationStatus(
                        item[
                            "status"
                        ]
                    )
                )

                record = (
                    CustomerSetupBuildContinuationRecord(
                        issuance_request_id=(
                            item[
                                "issuance_request_id"
                            ]
                        ),
                        continuation_id=(
                            item[
                                "continuation_id"
                            ]
                        ),
                        setup_activation_id=(
                            item[
                                "setup_activation_id"
                            ]
                        ),
                        deployment_id=(
                            item[
                                "deployment_id"
                            ]
                        ),
                        account_fingerprint_sha256=(
                            item[
                                "account_fingerprint_sha256"
                            ]
                        ),
                        verifier_sha256=(
                            item[
                                "verifier_sha256"
                            ]
                        ),
                        issued_at=(
                            item[
                                "issued_at"
                            ]
                        ),
                        expires_at=(
                            item[
                                "expires_at"
                            ]
                        ),
                        status=status,
                    )
                )
            except (
                KeyError,
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Customer setup build continuation "
                    "item is invalid."
                ) from error

            if (
                record.continuation_id
                in records
            ):
                raise ValueError(
                    "Duplicate customer setup build "
                    "continuation_id."
                )

            records[
                record.continuation_id
            ] = record

        self._validate_records(
            records
        )

        return records

    def _write_records(
        self,
        records: dict[
            str,
            CustomerSetupBuildContinuationRecord,
        ],
    ) -> None:
        self._validate_records(
            records
        )

        items = []

        for record in sorted(
            records.values(),
            key=lambda value: (
                value.continuation_id
            ),
        ):
            items.append(
                {
                    "issuance_request_id": (
                        record.issuance_request_id
                    ),
                    "continuation_id": (
                        record.continuation_id
                    ),
                    "setup_activation_id": (
                        record.setup_activation_id
                    ),
                    "deployment_id": (
                        record.deployment_id
                    ),
                    "account_fingerprint_sha256": (
                        record
                        .account_fingerprint_sha256
                    ),
                    "verifier_sha256": (
                        record.verifier_sha256
                    ),
                    "issued_at": (
                        record.issued_at
                    ),
                    "expires_at": (
                        record.expires_at
                    ),
                    "status": (
                        record.status.value
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "records": items,
        }

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.storage_path.with_name(
                "."
                + self.storage_path.name
                + "."
                + uuid.uuid4().hex
                + ".tmp"
            )
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as target:
                target.write(
                    json.dumps(
                        payload,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                )

                target.flush()
                os.fsync(
                    target.fileno()
                )

            os.replace(
                temporary_path,
                self.storage_path,
            )
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _validate_records(
        records: dict[
            str,
            CustomerSetupBuildContinuationRecord,
        ],
    ) -> None:
        issuance_ids: set[str] = set()
        verifiers: set[str] = set()
        active_activation_ids: set[str] = set()

        for key, record in records.items():
            if not isinstance(
                record,
                CustomerSetupBuildContinuationRecord,
            ):
                raise TypeError(
                    "Build continuation store contains "
                    "invalid record type."
                )

            if key != record.continuation_id:
                raise ValueError(
                    "Build continuation store key "
                    "identity mismatch."
                )

            if (
                record.issuance_request_id
                in issuance_ids
            ):
                raise ValueError(
                    "Duplicate build continuation "
                    "issuance_request_id."
                )

            issuance_ids.add(
                record.issuance_request_id
            )

            if (
                record.verifier_sha256
                in verifiers
            ):
                raise ValueError(
                    "Duplicate build continuation "
                    "verifier."
                )

            verifiers.add(
                record.verifier_sha256
            )

            if (
                record.status
                is CustomerSetupBuildContinuationStatus.ACTIVE
            ):
                if (
                    record.setup_activation_id
                    in active_activation_ids
                ):
                    raise ValueError(
                        "Multiple ACTIVE build "
                        "continuations reference one "
                        "setup activation."
                    )

                active_activation_ids.add(
                    record.setup_activation_id
                )


class CustomerSetupBuildContinuationService:
    """
    Issue, rotate, revoke, and authorize narrow build continuation
    credentials.

    Customer identity is never accepted from the caller.
    """

    def __init__(
        self,
        *,
        continuation_store: CustomerSetupBuildContinuationStore,
        setup_activation_store,
        build_request_store,
    ) -> None:
        if not isinstance(
            continuation_store,
            CustomerSetupBuildContinuationStore,
        ):
            raise TypeError(
                "continuation_store must be "
                "CustomerSetupBuildContinuationStore."
            )

        _require_owner_method(
            setup_activation_store,
            owner_name=(
                "setup_activation_store"
            ),
            method_name="get",
        )

        _require_owner_method(
            build_request_store,
            owner_name=(
                "build_request_store"
            ),
            method_name="get",
        )

        self._continuation_store = (
            continuation_store
        )
        self._setup_activation_store = (
            setup_activation_store
        )
        self._build_request_store = (
            build_request_store
        )
        self._lock = threading.RLock()

    def issue(
        self,
        *,
        setup_activation_id: str,
        deployment_id: str,
        account_fingerprint: str,
        current_time: datetime,
    ) -> CustomerSetupBuildContinuationIssuanceResult:
        normalized_activation_id = (
            _normalize_required_string(
                setup_activation_id,
                name="setup_activation_id",
            )
        )

        normalized_deployment_id = (
            _normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        normalized_account_fingerprint = (
            _normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        normalized_current_time = (
            _normalize_datetime(
                current_time
            )
        )

        account_fingerprint_sha256 = (
            derive_customer_setup_build_continuation_account_fingerprint(
                normalized_account_fingerprint
            )
        )

        issuance_request_id = (
            derive_customer_setup_build_continuation_issuance_request_id(
                setup_activation_id=(
                    normalized_activation_id
                ),
                deployment_id=(
                    normalized_deployment_id
                ),
            )
        )

        with self._lock:
            self._require_authoritative_state(
                setup_activation_id=(
                    normalized_activation_id
                ),
                deployment_id=(
                    normalized_deployment_id
                ),
            )

            existing = (
                self._continuation_store
                .get_by_issuance_request_id(
                    issuance_request_id=(
                        issuance_request_id
                    )
                )
            )

            if existing is not None:
                self._require_existing_identity(
                    existing=existing,
                    setup_activation_id=(
                        normalized_activation_id
                    ),
                    deployment_id=(
                        normalized_deployment_id
                    ),
                    account_fingerprint_sha256=(
                        account_fingerprint_sha256
                    ),
                )

                if (
                    existing.status
                    is CustomerSetupBuildContinuationStatus.REVOKED
                ):
                    raise ValueError(
                        "REVOKED customer setup build "
                        "continuation cannot be reissued."
                    )

                if self._is_expired(
                    existing,
                    normalized_current_time,
                ):
                    raise ValueError(
                        "Expired customer setup build "
                        "continuation cannot be reissued."
                    )

                return (
                    self._rotate_existing_secret(
                        existing
                    )
                )

            active = (
                self._continuation_store
                .get_active_by_setup_activation_id(
                    setup_activation_id=(
                        normalized_activation_id
                    )
                )
            )

            if active is not None:
                raise RuntimeError(
                    "Setup activation is already bound "
                    "to a different ACTIVE build "
                    "continuation identity."
                )

            return self._issue_new(
                issuance_request_id=(
                    issuance_request_id
                ),
                setup_activation_id=(
                    normalized_activation_id
                ),
                deployment_id=(
                    normalized_deployment_id
                ),
                account_fingerprint_sha256=(
                    account_fingerprint_sha256
                ),
                current_time=(
                    normalized_current_time
                ),
            )

    def authorize(
        self,
        *,
        continuation_credential: str,
        current_time: datetime,
        account_fingerprint: str | None = None,
    ) -> CustomerSetupBuildContinuationAuthorization:
        normalized_current_time = (
            _normalize_datetime(
                current_time
            )
        )

        (
            normalized_credential,
            continuation_id,
        ) = self._parse_credential(
            continuation_credential
        )

        with self._lock:
            record = (
                self._continuation_store.get(
                    continuation_id=(
                        continuation_id
                    )
                )
            )

            if record is None:
                raise ValueError(
                    "Invalid customer setup build "
                    "continuation credential."
                )

            supplied_verifier = (
                derive_customer_setup_build_continuation_verifier(
                    normalized_credential
                )
            )

            if not compare_digest(
                supplied_verifier,
                record.verifier_sha256,
            ):
                raise ValueError(
                    "Invalid customer setup build "
                    "continuation credential."
                )

            if (
                record.status
                is CustomerSetupBuildContinuationStatus.REVOKED
            ):
                raise ValueError(
                    "Customer setup build continuation "
                    "credential is revoked."
                )

            if self._is_expired(
                record,
                normalized_current_time,
            ):
                raise ValueError(
                    "Customer setup build continuation "
                    "credential is expired."
                )

            activation = (
                self._require_authoritative_state(
                    setup_activation_id=(
                        record.setup_activation_id
                    ),
                    deployment_id=(
                        record.deployment_id
                    ),
                )
            )

            if account_fingerprint is not None:
                supplied_account_hash = (
                    derive_customer_setup_build_continuation_account_fingerprint(
                        account_fingerprint
                    )
                )

                if not compare_digest(
                    supplied_account_hash,
                    record
                    .account_fingerprint_sha256,
                ):
                    raise ValueError(
                        "Customer setup build continuation "
                        "account fingerprint mismatch."
                    )

            customer_id = (
                _normalize_required_string(
                    getattr(
                        activation,
                        "customer_id",
                        None,
                    ),
                    name="customer_id",
                )
            )

            return (
                CustomerSetupBuildContinuationAuthorization(
                    continuation_id=(
                        record.continuation_id
                    ),
                    setup_activation_id=(
                        record.setup_activation_id
                    ),
                    customer_id=customer_id,
                    deployment_id=(
                        record.deployment_id
                    ),
                )
            )

    def revoke(
        self,
        *,
        continuation_id: str,
    ) -> CustomerSetupBuildContinuationRecord:
        with self._lock:
            return (
                self._continuation_store.revoke(
                    continuation_id=(
                        continuation_id
                    )
                )
            )

    def _require_authoritative_state(
        self,
        *,
        setup_activation_id: str,
        deployment_id: str,
    ):
        activation = (
            self._setup_activation_store.get(
                setup_activation_id=(
                    setup_activation_id
                )
            )
        )

        if activation is None:
            raise ValueError(
                "Unknown customer setup activation."
            )

        authoritative_activation_id = (
            getattr(
                activation,
                "setup_activation_id",
                None,
            )
        )

        if (
            authoritative_activation_id
            != setup_activation_id
        ):
            raise RuntimeError(
                "Customer setup activation identity "
                "mismatch."
            )

        status = getattr(
            activation,
            "status",
            None,
        )

        if (
            status
            is CustomerSetupActivationStatus.SUSPENDED
        ):
            raise ValueError(
                "Customer setup activation is SUSPENDED."
            )

        if status not in {
            CustomerSetupActivationStatus.ACTIVE,
            CustomerSetupActivationStatus.BOUND,
        }:
            raise RuntimeError(
                "Unsupported customer setup activation "
                "status."
            )

        activation_deployment_id = (
            getattr(
                activation,
                "deployment_id",
                None,
            )
        )

        if (
            status
            is CustomerSetupActivationStatus.ACTIVE
        ):
            if activation_deployment_id is not None:
                raise RuntimeError(
                    "ACTIVE customer setup activation "
                    "must not claim deployment identity."
                )

        elif (
            activation_deployment_id
            != deployment_id
        ):
            raise ValueError(
                "BOUND customer setup activation "
                "deployment identity mismatch."
            )

        customer_id = getattr(
            activation,
            "customer_id",
            None,
        )

        _normalize_required_string(
            customer_id,
            name="customer_id",
        )

        build_request = (
            self._build_request_store.get(
                deployment_id=(
                    deployment_id
                )
            )
        )

        if build_request is None:
            raise RuntimeError(
                "Customer deployment package build "
                "request is missing."
            )

        if not isinstance(
            build_request,
            CustomerDeploymentPackageBuildRequest,
        ):
            raise RuntimeError(
                "Package build request owner returned "
                "invalid result."
            )

        if (
            build_request.deployment_id
            != deployment_id
        ):
            raise RuntimeError(
                "Package build request deployment "
                "identity mismatch."
            )

        if (
            build_request.bootstrap_request_id
            != setup_activation_id
        ):
            raise RuntimeError(
                "Package build request bootstrap "
                "identity mismatch."
            )

        return activation

    @staticmethod
    def _require_existing_identity(
        *,
        existing: CustomerSetupBuildContinuationRecord,
        setup_activation_id: str,
        deployment_id: str,
        account_fingerprint_sha256: str,
    ) -> None:
        if (
            existing.setup_activation_id
            != setup_activation_id
        ):
            raise RuntimeError(
                "Build continuation setup activation "
                "identity mismatch."
            )

        if (
            existing.deployment_id
            != deployment_id
        ):
            raise RuntimeError(
                "Build continuation deployment "
                "identity mismatch."
            )

        if not compare_digest(
            existing.account_fingerprint_sha256,
            account_fingerprint_sha256,
        ):
            raise ValueError(
                "Build continuation account fingerprint "
                "identity mismatch."
            )

    def _issue_new(
        self,
        *,
        issuance_request_id: str,
        setup_activation_id: str,
        deployment_id: str,
        account_fingerprint_sha256: str,
        current_time: datetime,
    ) -> CustomerSetupBuildContinuationIssuanceResult:
        issued_at = _serialize_timestamp(
            current_time
        )

        expires_at = _serialize_timestamp(
            current_time
            + _CONTINUATION_TTL
        )

        for _ in range(
            _GENERATION_ATTEMPTS
        ):
            continuation_id = (
                secrets.token_hex(
                    _CONTINUATION_ID_RANDOM_BYTES
                )
            )

            if (
                self._continuation_store.get(
                    continuation_id=(
                        continuation_id
                    )
                )
                is not None
            ):
                continue

            continuation_credential = (
                self._generate_credential(
                    continuation_id=(
                        continuation_id
                    )
                )
            )

            verifier = (
                derive_customer_setup_build_continuation_verifier(
                    continuation_credential
                )
            )

            if (
                self._continuation_store
                .get_by_verifier(
                    verifier_sha256=(
                        verifier
                    )
                )
                is not None
            ):
                continue

            record = (
                CustomerSetupBuildContinuationRecord(
                    issuance_request_id=(
                        issuance_request_id
                    ),
                    continuation_id=(
                        continuation_id
                    ),
                    setup_activation_id=(
                        setup_activation_id
                    ),
                    deployment_id=(
                        deployment_id
                    ),
                    account_fingerprint_sha256=(
                        account_fingerprint_sha256
                    ),
                    verifier_sha256=verifier,
                    issued_at=issued_at,
                    expires_at=expires_at,
                    status=(
                        CustomerSetupBuildContinuationStatus
                        .ACTIVE
                    ),
                )
            )

            persisted = (
                self._continuation_store.add(
                    record
                )
            )

            return self._build_issuance_result(
                record=persisted,
                continuation_credential=(
                    continuation_credential
                ),
            )

        raise RuntimeError(
            "Unable to generate unique customer setup "
            "build continuation credential."
        )

    def _rotate_existing_secret(
        self,
        record: CustomerSetupBuildContinuationRecord,
    ) -> CustomerSetupBuildContinuationIssuanceResult:
        for _ in range(
            _GENERATION_ATTEMPTS
        ):
            continuation_credential = (
                self._generate_credential(
                    continuation_id=(
                        record.continuation_id
                    )
                )
            )

            verifier = (
                derive_customer_setup_build_continuation_verifier(
                    continuation_credential
                )
            )

            verifier_owner = (
                self._continuation_store
                .get_by_verifier(
                    verifier_sha256=verifier
                )
            )

            if (
                verifier_owner is not None
                and verifier_owner.continuation_id
                != record.continuation_id
            ):
                continue

            updated = (
                self._continuation_store
                .rotate_verifier(
                    continuation_id=(
                        record.continuation_id
                    ),
                    verifier_sha256=verifier,
                )
            )

            return self._build_issuance_result(
                record=updated,
                continuation_credential=(
                    continuation_credential
                ),
            )

        raise RuntimeError(
            "Unable to rotate customer setup build "
            "continuation credential."
        )

    @staticmethod
    def _generate_credential(
        *,
        continuation_id: str,
    ) -> str:
        secret = secrets.token_urlsafe(
            _CONTINUATION_SECRET_RANDOM_BYTES
        )

        return (
            f"{_CONTINUATION_PREFIX}."
            f"{continuation_id}."
            f"{secret}"
        )

    @staticmethod
    def _parse_credential(
        continuation_credential: str,
    ) -> tuple[
        str,
        str,
    ]:
        normalized = _normalize_required_string(
            continuation_credential,
            name="continuation_credential",
        )

        parts = normalized.split(
            "."
        )

        if len(parts) != 3:
            raise ValueError(
                "Invalid customer setup build "
                "continuation credential."
            )

        prefix, continuation_id, secret = (
            parts
        )

        if prefix != _CONTINUATION_PREFIX:
            raise ValueError(
                "Invalid customer setup build "
                "continuation credential."
            )

        if not _CONTINUATION_ID_PATTERN.fullmatch(
            continuation_id
        ):
            raise ValueError(
                "Invalid customer setup build "
                "continuation credential."
            )

        if (
            len(secret) < 32
            or not _SECRET_PATTERN.fullmatch(
                secret
            )
        ):
            raise ValueError(
                "Invalid customer setup build "
                "continuation credential."
            )

        return (
            normalized,
            continuation_id,
        )

    @staticmethod
    def _is_expired(
        record: CustomerSetupBuildContinuationRecord,
        current_time: datetime,
    ) -> bool:
        expires_at = _parse_timestamp(
            record.expires_at,
            name="expires_at",
        )

        return (
            _normalize_datetime(
                current_time
            )
            >= expires_at
        )

    @staticmethod
    def _build_issuance_result(
        *,
        record: CustomerSetupBuildContinuationRecord,
        continuation_credential: str,
    ) -> CustomerSetupBuildContinuationIssuanceResult:
        return (
            CustomerSetupBuildContinuationIssuanceResult(
                issuance_request_id=(
                    record.issuance_request_id
                ),
                continuation_id=(
                    record.continuation_id
                ),
                setup_activation_id=(
                    record.setup_activation_id
                ),
                deployment_id=(
                    record.deployment_id
                ),
                issued_at=record.issued_at,
                expires_at=record.expires_at,
                continuation_credential=(
                    continuation_credential
                ),
            )
        )


def _require_owner_method(
    owner,
    *,
    owner_name: str,
    method_name: str,
) -> None:
    method = getattr(
        owner,
        method_name,
        None,
    )

    if not callable(
        method
    ):
        raise TypeError(
            f"{owner_name}.{method_name} "
            "must be callable."
        )


def _normalize_required_string(
    value,
    *,
    name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be str."
        )

    normalized = value.strip()

    if (
        not normalized
        or normalized != value
    ):
        raise ValueError(
            f"{name} is invalid."
        )

    return normalized


def _normalize_sha256(
    value,
    *,
    name: str,
) -> str:
    normalized = (
        _normalize_required_string(
            value,
            name=name,
        )
        .lower()
    )

    if not _SHA256_PATTERN.fullmatch(
        normalized
    ):
        raise ValueError(
            f"{name} must be a SHA-256 "
            "hexadecimal digest."
        )

    return normalized


def _normalize_datetime(
    value: datetime,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "current_time must be datetime."
        )

    if value.tzinfo is None:
        raise ValueError(
            "current_time must be timezone-aware."
        )

    return value.astimezone(
        timezone.utc
    )


def _serialize_timestamp(
    value: datetime,
) -> str:
    normalized = _normalize_datetime(
        value
    )

    return (
        normalized.isoformat(
            timespec="microseconds"
        )
        .replace(
            "+00:00",
            "Z",
        )
    )


def _normalize_timestamp(
    value,
    *,
    name: str,
) -> str:
    parsed = _parse_timestamp(
        value,
        name=name,
    )

    return _serialize_timestamp(
        parsed
    )


def _parse_timestamp(
    value,
    *,
    name: str,
) -> datetime:
    normalized = _normalize_required_string(
        value,
        name=name,
    )

    try:
        parsed = datetime.fromisoformat(
            normalized.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError as error:
        raise ValueError(
            f"{name} is invalid."
        ) from error

    if parsed.tzinfo is None:
        raise ValueError(
            f"{name} must be timezone-aware."
        )

    return parsed.astimezone(
        timezone.utc
    )
