"""
TODOBA Customer Setup Launch Credential

Pre-deployment authorization credential used only to enter
the TODOBA customer Setup flow.

Ownership:
- one launch issuance request is bound to one customer
- plaintext launch credentials are never persisted
- durable state stores only SHA-256 credential verifiers
- credentials are short-lived and revocable
- retry rotates plaintext secret while preserving launch
  identity and original lifetime
- authorization returns the authoritative customer identity

This owner does not expose HTTP and does not grant setup
activation, handoff, package, runtime, or trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from enum import Enum
from hashlib import sha256
from hmac import compare_digest
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading

from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)


STORE_VERSION = 1

_LAUNCH_PREFIX = "tdbsl"
_LAUNCH_ID_RANDOM_BYTES = 16
_LAUNCH_SECRET_RANDOM_BYTES = 32
_LAUNCH_TTL = timedelta(
    minutes=15
)
_GENERATION_ATTEMPTS = 32

_HEX_32_PATTERN = re.compile(
    r"^[0-9a-f]{32}$"
)
_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)
_SECRET_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{32,}$"
)


class CustomerSetupLaunchCredentialStatus(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(
    frozen=True,
)
class CustomerSetupLaunchCredentialRecord:
    """
    Durable non-secret launch credential record.
    """

    issuance_request_id: str
    launch_id: str
    customer_id: str
    verifier_sha256: str
    issued_at: str
    expires_at: str
    status: CustomerSetupLaunchCredentialStatus

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "issuance_request_id",
            _normalize_required_string(
                self.issuance_request_id,
                name="issuance_request_id",
            ),
        )
        object.__setattr__(
            self,
            "launch_id",
            _normalize_launch_id(
                self.launch_id
            ),
        )
        object.__setattr__(
            self,
            "customer_id",
            _normalize_required_string(
                self.customer_id,
                name="customer_id",
            ),
        )
        object.__setattr__(
            self,
            "verifier_sha256",
            _normalize_verifier(
                self.verifier_sha256
            ),
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

        object.__setattr__(
            self,
            "issued_at",
            _serialize_timestamp(
                issued_at
            ),
        )
        object.__setattr__(
            self,
            "expires_at",
            _serialize_timestamp(
                expires_at
            ),
        )

        if not isinstance(
            self.status,
            CustomerSetupLaunchCredentialStatus,
        ):
            try:
                normalized_status = (
                    CustomerSetupLaunchCredentialStatus(
                        self.status
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Invalid customer setup launch "
                    "credential status."
                ) from error

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )


@dataclass(
    frozen=True,
    repr=False,
)
class CustomerSetupLaunchCredentialIssuanceResult:
    """
    One plaintext launch credential returned after durable
    verifier persistence succeeds.
    """

    issuance_request_id: str
    launch_id: str
    customer_id: str
    issued_at: str
    expires_at: str
    launch_credential: str = field(
        repr=False
    )

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "issuance_request_id",
            "customer_id",
            "launch_credential",
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

        object.__setattr__(
            self,
            "launch_id",
            _normalize_launch_id(
                self.launch_id
            ),
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

        object.__setattr__(
            self,
            "issued_at",
            _serialize_timestamp(
                issued_at
            ),
        )
        object.__setattr__(
            self,
            "expires_at",
            _serialize_timestamp(
                expires_at
            ),
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupLaunchCredentialIssuanceResult("
            f"issuance_request_id="
            f"{self.issuance_request_id!r}, "
            f"launch_id={self.launch_id!r}, "
            f"customer_id={self.customer_id!r}, "
            f"issued_at={self.issued_at!r}, "
            f"expires_at={self.expires_at!r}, "
            "launch_credential=<redacted>)"
        )


@dataclass(
    frozen=True,
)
class CustomerSetupLaunchAuthorization:
    """
    Safe authoritative result of one launch credential
    authorization.
    """

    launch_id: str
    customer_id: str
    issued_at: str
    expires_at: str

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "launch_id",
            _normalize_launch_id(
                self.launch_id
            ),
        )
        object.__setattr__(
            self,
            "customer_id",
            _normalize_required_string(
                self.customer_id,
                name="customer_id",
            ),
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

        object.__setattr__(
            self,
            "issued_at",
            _serialize_timestamp(
                issued_at
            ),
        )
        object.__setattr__(
            self,
            "expires_at",
            _serialize_timestamp(
                expires_at
            ),
        )


def derive_customer_setup_launch_verifier(
    launch_credential: str,
) -> str:
    normalized = _normalize_required_string(
        launch_credential,
        name="launch_credential",
    )

    return sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


class CustomerSetupLaunchCredentialStore:
    """
    Durable authoritative owner of setup launch credential
    verifiers.
    """

    def __init__(
        self,
        storage_path: Path,
        *,
        customer_identity_registry: CustomerIdentityRegistry,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        if not isinstance(
            customer_identity_registry,
            CustomerIdentityRegistry,
        ):
            raise TypeError(
                "customer_identity_registry must be "
                "CustomerIdentityRegistry."
            )

        if not customer_identity_registry.is_ready():
            raise RuntimeError(
                "Customer identity registry is not "
                "initialized."
            )

        self.storage_path = storage_path
        self._customer_identity_registry = (
            customer_identity_registry
        )

        self._records: dict[
            str,
            CustomerSetupLaunchCredentialRecord,
        ] = {}

        self._launch_id_by_issuance_request_id: dict[
            str,
            str,
        ] = {}

        self._launch_id_by_verifier: dict[
            str,
            str,
        ] = {}

        self._ready = False
        self._lock = threading.RLock()

    def initialize_empty(
        self,
    ) -> None:
        with self._lock:
            if self._ready:
                return

            if self.storage_path.exists():
                raise FileExistsError(
                    "Customer setup launch credential "
                    "store already exists."
                )

            records: dict[
                str,
                CustomerSetupLaunchCredentialRecord,
            ] = {}

            self._write_records(
                records
            )
            self._install_candidate(
                records
            )
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if self._ready:
                return

            if not self.storage_path.is_file():
                raise FileNotFoundError(
                    "Customer setup launch credential "
                    "store does not exist."
                )

            self._restore_from_disk()

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        record: CustomerSetupLaunchCredentialRecord,
    ) -> CustomerSetupLaunchCredentialRecord:
        if not isinstance(
            record,
            CustomerSetupLaunchCredentialRecord,
        ):
            raise TypeError(
                "register requires "
                "CustomerSetupLaunchCredentialRecord."
            )

        with self._lock:
            self._require_ready()
            self._require_known_customer(
                record.customer_id
            )

            existing_by_request = (
                self.get_by_issuance_request_id(
                    issuance_request_id=(
                        record.issuance_request_id
                    )
                )
            )

            if existing_by_request is not None:
                if existing_by_request == record:
                    return existing_by_request

                raise ValueError(
                    "Customer setup launch issuance "
                    "request is already assigned."
                )

            existing_by_id = self._records.get(
                record.launch_id
            )

            if existing_by_id is not None:
                if existing_by_id == record:
                    return existing_by_id

                raise ValueError(
                    "Customer setup launch_id is "
                    "already assigned."
                )

            verifier_owner = (
                self.get_by_verifier(
                    verifier_sha256=(
                        record.verifier_sha256
                    )
                )
            )

            if verifier_owner is not None:
                if verifier_owner == record:
                    return verifier_owner

                raise ValueError(
                    "Customer setup launch verifier is "
                    "already assigned."
                )

            candidate = dict(
                self._records
            )
            candidate[
                record.launch_id
            ] = record

            self._validate_candidate(
                candidate
            )
            self._write_records(
                candidate
            )
            self._install_candidate(
                candidate
            )

            return record

    def rotate_verifier(
        self,
        *,
        launch_id: str,
        verifier_sha256: str,
    ) -> CustomerSetupLaunchCredentialRecord:
        normalized_launch_id = (
            _normalize_launch_id(
                launch_id
            )
        )
        normalized_verifier = (
            _normalize_verifier(
                verifier_sha256
            )
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                normalized_launch_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown customer setup launch_id."
                )

            if (
                existing.status
                is CustomerSetupLaunchCredentialStatus
                .REVOKED
            ):
                raise ValueError(
                    "REVOKED customer setup launch "
                    "credential cannot be rotated."
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
                and verifier_owner.launch_id
                != normalized_launch_id
            ):
                raise ValueError(
                    "Customer setup launch verifier is "
                    "already assigned."
                )

            if (
                existing.verifier_sha256
                == normalized_verifier
            ):
                return existing

            updated = (
                CustomerSetupLaunchCredentialRecord(
                    issuance_request_id=(
                        existing.issuance_request_id
                    ),
                    launch_id=existing.launch_id,
                    customer_id=existing.customer_id,
                    verifier_sha256=(
                        normalized_verifier
                    ),
                    issued_at=existing.issued_at,
                    expires_at=existing.expires_at,
                    status=existing.status,
                )
            )

            candidate = dict(
                self._records
            )
            candidate[
                normalized_launch_id
            ] = updated

            self._validate_candidate(
                candidate
            )
            self._write_records(
                candidate
            )
            self._install_candidate(
                candidate
            )

            return updated

    def revoke(
        self,
        *,
        launch_id: str,
    ) -> CustomerSetupLaunchCredentialRecord:
        normalized_launch_id = (
            _normalize_launch_id(
                launch_id
            )
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                normalized_launch_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown customer setup launch_id."
                )

            if (
                existing.status
                is CustomerSetupLaunchCredentialStatus
                .REVOKED
            ):
                return existing

            updated = (
                CustomerSetupLaunchCredentialRecord(
                    issuance_request_id=(
                        existing.issuance_request_id
                    ),
                    launch_id=existing.launch_id,
                    customer_id=existing.customer_id,
                    verifier_sha256=(
                        existing.verifier_sha256
                    ),
                    issued_at=existing.issued_at,
                    expires_at=existing.expires_at,
                    status=(
                        CustomerSetupLaunchCredentialStatus
                        .REVOKED
                    ),
                )
            )

            candidate = dict(
                self._records
            )
            candidate[
                normalized_launch_id
            ] = updated

            self._validate_candidate(
                candidate
            )
            self._write_records(
                candidate
            )
            self._install_candidate(
                candidate
            )

            return updated

    def get(
        self,
        *,
        launch_id: str,
    ) -> CustomerSetupLaunchCredentialRecord | None:
        self._require_ready()

        normalized_launch_id = (
            _normalize_launch_id(
                launch_id
            )
        )

        return self._records.get(
            normalized_launch_id
        )

    def get_by_issuance_request_id(
        self,
        *,
        issuance_request_id: str,
    ) -> CustomerSetupLaunchCredentialRecord | None:
        self._require_ready()

        normalized_request_id = (
            _normalize_required_string(
                issuance_request_id,
                name="issuance_request_id",
            )
        )

        launch_id = (
            self._launch_id_by_issuance_request_id
            .get(
                normalized_request_id
            )
        )

        if launch_id is None:
            return None

        return self._records[
            launch_id
        ]

    def get_by_verifier(
        self,
        *,
        verifier_sha256: str,
    ) -> CustomerSetupLaunchCredentialRecord | None:
        self._require_ready()

        normalized_verifier = (
            _normalize_verifier(
                verifier_sha256
            )
        )

        launch_id = (
            self._launch_id_by_verifier.get(
                normalized_verifier
            )
        )

        if launch_id is None:
            return None

        return self._records[
            launch_id
        ]

    def all(
        self,
    ) -> tuple[
        CustomerSetupLaunchCredentialRecord,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._records[
                launch_id
            ]
            for launch_id in sorted(
                self._records
            )
        )

    def size(
        self,
    ) -> int:
        self._require_ready()
        return len(
            self._records
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer setup launch credential "
                "store is not initialized."
            )

    def _require_known_customer(
        self,
        customer_id: str,
    ) -> CustomerIdentity:
        identity = (
            self._customer_identity_registry.get(
                customer_id=customer_id
            )
        )

        if identity is None:
            raise ValueError(
                "Customer setup launch credential "
                "references unknown customer."
            )

        return identity

    def _validate_candidate(
        self,
        records: dict[
            str,
            CustomerSetupLaunchCredentialRecord,
        ],
    ) -> tuple[
        dict[str, str],
        dict[str, str],
    ]:
        request_index: dict[
            str,
            str,
        ] = {}
        verifier_index: dict[
            str,
            str,
        ] = {}

        for launch_id, record in records.items():
            if launch_id != record.launch_id:
                raise ValueError(
                    "Customer setup launch record key "
                    "does not match launch_id."
                )

            self._require_known_customer(
                record.customer_id
            )

            if (
                record.issuance_request_id
                in request_index
            ):
                raise ValueError(
                    "Duplicate customer setup launch "
                    "issuance request."
                )

            if (
                record.verifier_sha256
                in verifier_index
            ):
                raise ValueError(
                    "Duplicate customer setup launch "
                    "verifier."
                )

            request_index[
                record.issuance_request_id
            ] = record.launch_id

            verifier_index[
                record.verifier_sha256
            ] = record.launch_id

        return (
            request_index,
            verifier_index,
        )

    def _install_candidate(
        self,
        records: dict[
            str,
            CustomerSetupLaunchCredentialRecord,
        ],
    ) -> None:
        (
            request_index,
            verifier_index,
        ) = self._validate_candidate(
            records
        )

        self._records = records
        self._launch_id_by_issuance_request_id = (
            request_index
        )
        self._launch_id_by_verifier = (
            verifier_index
        )

    def _restore_from_disk(
        self,
    ) -> None:
        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer setup launch credential "
                "payload must be an object."
            )

        if set(
            payload
        ) != {
            "version",
            "records",
        }:
            raise ValueError(
                "Customer setup launch credential "
                "payload has invalid fields."
            )

        if payload.get(
            "version"
        ) != STORE_VERSION:
            raise ValueError(
                "Unsupported customer setup launch "
                "credential store version."
            )

        items = payload.get(
            "records"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer setup launch credential "
                "records must be a list."
            )

        restored: dict[
            str,
            CustomerSetupLaunchCredentialRecord,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer setup launch credential "
                    "item must be an object."
                )

            if set(
                item
            ) != {
                "issuance_request_id",
                "launch_id",
                "customer_id",
                "verifier_sha256",
                "issued_at",
                "expires_at",
                "status",
            }:
                raise ValueError(
                    "Customer setup launch credential "
                    "item has invalid fields."
                )

            record = (
                CustomerSetupLaunchCredentialRecord(
                    issuance_request_id=item[
                        "issuance_request_id"
                    ],
                    launch_id=item[
                        "launch_id"
                    ],
                    customer_id=item[
                        "customer_id"
                    ],
                    verifier_sha256=item[
                        "verifier_sha256"
                    ],
                    issued_at=item[
                        "issued_at"
                    ],
                    expires_at=item[
                        "expires_at"
                    ],
                    status=item[
                        "status"
                    ],
                )
            )

            if record.launch_id in restored:
                raise ValueError(
                    "Duplicate customer setup "
                    "launch_id."
                )

            restored[
                record.launch_id
            ] = record

        self._install_candidate(
            restored
        )
        self._ready = True

    def _write_records(
        self,
        records: dict[
            str,
            CustomerSetupLaunchCredentialRecord,
        ],
    ) -> None:
        items = []

        for launch_id in sorted(
            records
        ):
            record = records[
                launch_id
            ]

            items.append(
                {
                    "issuance_request_id": (
                        record.issuance_request_id
                    ),
                    "launch_id": (
                        record.launch_id
                    ),
                    "customer_id": (
                        record.customer_id
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

        serialized = (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        descriptor, temporary_name = (
            tempfile.mkstemp(
                prefix=(
                    f".{self.storage_path.name}."
                ),
                suffix=".tmp",
                dir=str(
                    self.storage_path.parent
                ),
                text=True,
            )
        )

        temporary_path = Path(
            temporary_name
        )

        try:
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(
                    serialized
                )
                handle.flush()
                os.fsync(
                    handle.fileno()
                )

            os.replace(
                temporary_path,
                self.storage_path,
            )
        finally:
            if temporary_path.exists():
                temporary_path.unlink()


class CustomerSetupLaunchCredentialService:
    """
    Issue, recover, authorize, and revoke short-lived
    customer setup launch credentials.
    """

    def __init__(
        self,
        *,
        launch_store: CustomerSetupLaunchCredentialStore,
        customer_identity_registry: CustomerIdentityRegistry,
    ) -> None:
        if not isinstance(
            launch_store,
            CustomerSetupLaunchCredentialStore,
        ):
            raise TypeError(
                "launch_store must be "
                "CustomerSetupLaunchCredentialStore."
            )

        if not isinstance(
            customer_identity_registry,
            CustomerIdentityRegistry,
        ):
            raise TypeError(
                "customer_identity_registry must be "
                "CustomerIdentityRegistry."
            )

        if not launch_store.is_ready():
            raise RuntimeError(
                "Customer setup launch credential "
                "store is not initialized."
            )

        if not customer_identity_registry.is_ready():
            raise RuntimeError(
                "Customer identity registry is not "
                "initialized."
            )

        self._launch_store = launch_store
        self._customer_identity_registry = (
            customer_identity_registry
        )
        self._lock = threading.RLock()

    def issue(
        self,
        *,
        issuance_request_id: str,
        customer_id: str,
        current_time: datetime,
    ) -> CustomerSetupLaunchCredentialIssuanceResult:
        """
        Issue or recover one launch credential.

        Existing request retry:
        - same launch_id
        - rotated plaintext secret and verifier
        - unchanged issued_at
        - unchanged expires_at

        Retry never revives a revoked or expired credential.
        """

        normalized_request_id = (
            _normalize_required_string(
                issuance_request_id,
                name="issuance_request_id",
            )
        )
        normalized_customer_id = (
            _normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )
        normalized_current_time = (
            _normalize_datetime(
                current_time
            )
        )

        with self._lock:
            self._require_sources_ready()

            identity = (
                self._customer_identity_registry.get(
                    customer_id=(
                        normalized_customer_id
                    )
                )
            )

            if identity is None:
                raise ValueError(
                    "Customer is not authoritatively "
                    "registered."
                )

            existing = (
                self._launch_store
                .get_by_issuance_request_id(
                    issuance_request_id=(
                        normalized_request_id
                    )
                )
            )

            if existing is not None:
                if (
                    existing.customer_id
                    != normalized_customer_id
                ):
                    raise ValueError(
                        "Customer setup launch issuance "
                        "request is already assigned to "
                        "another customer."
                    )

                if (
                    existing.status
                    is CustomerSetupLaunchCredentialStatus
                    .REVOKED
                ):
                    raise ValueError(
                        "REVOKED customer setup launch "
                        "credential cannot be reissued."
                    )

                if self._is_expired(
                    existing,
                    normalized_current_time,
                ):
                    raise ValueError(
                        "Expired customer setup launch "
                        "credential cannot be reissued."
                    )

                return (
                    self._rotate_existing_secret(
                        existing
                    )
                )

            return self._issue_new(
                issuance_request_id=(
                    normalized_request_id
                ),
                customer_id=(
                    normalized_customer_id
                ),
                current_time=(
                    normalized_current_time
                ),
            )

    def authorize(
        self,
        *,
        launch_credential: str,
        current_time: datetime,
    ) -> CustomerSetupLaunchAuthorization:
        """
        Authorize one supplied launch credential without
        mutating durable state.
        """

        normalized_current_time = (
            _normalize_datetime(
                current_time
            )
        )

        (
            normalized_credential,
            launch_id,
        ) = self._parse_credential(
            launch_credential
        )

        with self._lock:
            self._require_sources_ready()

            record = self._launch_store.get(
                launch_id=launch_id
            )

            if record is None:
                raise ValueError(
                    "Invalid customer setup launch "
                    "credential."
                )

            supplied_verifier = (
                derive_customer_setup_launch_verifier(
                    normalized_credential
                )
            )

            if not compare_digest(
                supplied_verifier,
                record.verifier_sha256,
            ):
                raise ValueError(
                    "Invalid customer setup launch "
                    "credential."
                )

            if (
                record.status
                is CustomerSetupLaunchCredentialStatus
                .REVOKED
            ):
                raise ValueError(
                    "Customer setup launch credential "
                    "is revoked."
                )

            if self._is_expired(
                record,
                normalized_current_time,
            ):
                raise ValueError(
                    "Customer setup launch credential "
                    "is expired."
                )

            identity = (
                self._customer_identity_registry.get(
                    customer_id=(
                        record.customer_id
                    )
                )
            )

            if identity is None:
                raise RuntimeError(
                    "Customer setup launch credential "
                    "references missing authoritative "
                    "customer."
                )

            if (
                identity.customer_id
                != record.customer_id
            ):
                raise RuntimeError(
                    "Customer setup launch identity "
                    "did not converge."
                )

            return CustomerSetupLaunchAuthorization(
                launch_id=record.launch_id,
                customer_id=identity.customer_id,
                issued_at=record.issued_at,
                expires_at=record.expires_at,
            )

    def revoke(
        self,
        *,
        launch_id: str,
    ) -> CustomerSetupLaunchCredentialRecord:
        with self._lock:
            self._require_sources_ready()

            return self._launch_store.revoke(
                launch_id=launch_id
            )

    def get(
        self,
        *,
        launch_id: str,
    ) -> CustomerSetupLaunchCredentialRecord | None:
        self._require_sources_ready()

        return self._launch_store.get(
            launch_id=launch_id
        )

    def _issue_new(
        self,
        *,
        issuance_request_id: str,
        customer_id: str,
        current_time: datetime,
    ) -> CustomerSetupLaunchCredentialIssuanceResult:
        issued_at = _serialize_timestamp(
            current_time
        )
        expires_at = _serialize_timestamp(
            current_time
            + _LAUNCH_TTL
        )

        for _ in range(
            _GENERATION_ATTEMPTS
        ):
            launch_id = secrets.token_hex(
                _LAUNCH_ID_RANDOM_BYTES
            )

            if (
                self._launch_store.get(
                    launch_id=launch_id
                )
                is not None
            ):
                continue

            launch_credential = (
                self._generate_credential(
                    launch_id=launch_id
                )
            )

            verifier = (
                derive_customer_setup_launch_verifier(
                    launch_credential
                )
            )

            if (
                self._launch_store.get_by_verifier(
                    verifier_sha256=verifier
                )
                is not None
            ):
                continue

            record = (
                CustomerSetupLaunchCredentialRecord(
                    issuance_request_id=(
                        issuance_request_id
                    ),
                    launch_id=launch_id,
                    customer_id=customer_id,
                    verifier_sha256=verifier,
                    issued_at=issued_at,
                    expires_at=expires_at,
                    status=(
                        CustomerSetupLaunchCredentialStatus
                        .ACTIVE
                    ),
                )
            )

            persisted = (
                self._launch_store.register(
                    record
                )
            )

            return self._build_issuance_result(
                record=persisted,
                launch_credential=(
                    launch_credential
                ),
            )

        raise RuntimeError(
            "Unable to generate unique customer setup "
            "launch credential."
        )

    def _rotate_existing_secret(
        self,
        record: CustomerSetupLaunchCredentialRecord,
    ) -> CustomerSetupLaunchCredentialIssuanceResult:
        for _ in range(
            _GENERATION_ATTEMPTS
        ):
            launch_credential = (
                self._generate_credential(
                    launch_id=(
                        record.launch_id
                    )
                )
            )

            verifier = (
                derive_customer_setup_launch_verifier(
                    launch_credential
                )
            )

            verifier_owner = (
                self._launch_store
                .get_by_verifier(
                    verifier_sha256=verifier
                )
            )

            if (
                verifier_owner is not None
                and verifier_owner.launch_id
                != record.launch_id
            ):
                continue

            updated = (
                self._launch_store.rotate_verifier(
                    launch_id=record.launch_id,
                    verifier_sha256=verifier,
                )
            )

            return self._build_issuance_result(
                record=updated,
                launch_credential=(
                    launch_credential
                ),
            )

        raise RuntimeError(
            "Unable to rotate customer setup launch "
            "credential."
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._launch_store.is_ready():
            raise RuntimeError(
                "Customer setup launch credential "
                "store is not initialized."
            )

        if not self._customer_identity_registry.is_ready():
            raise RuntimeError(
                "Customer identity registry is not "
                "initialized."
            )

    @staticmethod
    def _generate_credential(
        *,
        launch_id: str,
    ) -> str:
        normalized_launch_id = (
            _normalize_launch_id(
                launch_id
            )
        )

        secret = secrets.token_urlsafe(
            _LAUNCH_SECRET_RANDOM_BYTES
        )

        return (
            f"{_LAUNCH_PREFIX}."
            f"{normalized_launch_id}."
            f"{secret}"
        )

    @staticmethod
    def _parse_credential(
        launch_credential: str,
    ) -> tuple[
        str,
        str,
    ]:
        normalized = (
            _normalize_required_string(
                launch_credential,
                name="launch_credential",
            )
        )

        parts = normalized.split(
            "."
        )

        if len(
            parts
        ) != 3:
            raise ValueError(
                "Invalid customer setup launch "
                "credential."
            )

        prefix, launch_id, secret = parts

        if prefix != _LAUNCH_PREFIX:
            raise ValueError(
                "Invalid customer setup launch "
                "credential."
            )

        try:
            normalized_launch_id = (
                _normalize_launch_id(
                    launch_id
                )
            )
        except ValueError as error:
            raise ValueError(
                "Invalid customer setup launch "
                "credential."
            ) from error

        if not _SECRET_PATTERN.fullmatch(
            secret
        ):
            raise ValueError(
                "Invalid customer setup launch "
                "credential."
            )

        return (
            normalized,
            normalized_launch_id,
        )

    @staticmethod
    def _is_expired(
        record: CustomerSetupLaunchCredentialRecord,
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
        record: CustomerSetupLaunchCredentialRecord,
        launch_credential: str,
    ) -> CustomerSetupLaunchCredentialIssuanceResult:
        return (
            CustomerSetupLaunchCredentialIssuanceResult(
                issuance_request_id=(
                    record.issuance_request_id
                ),
                launch_id=record.launch_id,
                customer_id=record.customer_id,
                issued_at=record.issued_at,
                expires_at=record.expires_at,
                launch_credential=(
                    launch_credential
                ),
            )
        )


def _normalize_required_string(
    value: str,
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

    if not normalized:
        raise ValueError(
            f"{name} is required."
        )

    return normalized


def _normalize_launch_id(
    value: str,
) -> str:
    normalized = (
        _normalize_required_string(
            value,
            name="launch_id",
        ).lower()
    )

    if not _HEX_32_PATTERN.fullmatch(
        normalized
    ):
        raise ValueError(
            "Invalid customer setup launch_id."
        )

    return normalized


def _normalize_verifier(
    value: str,
) -> str:
    normalized = (
        _normalize_required_string(
            value,
            name="verifier_sha256",
        ).lower()
    )

    if not _SHA256_PATTERN.fullmatch(
        normalized
    ):
        raise ValueError(
            "Invalid customer setup launch verifier."
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

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            "current_time must be timezone-aware."
        )

    return value.astimezone(
        timezone.utc
    )


def _serialize_timestamp(
    value: datetime,
) -> str:
    normalized = value.astimezone(
        timezone.utc
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


def _parse_timestamp(
    value: str,
    *,
    name: str,
) -> datetime:
    normalized = (
        _normalize_required_string(
            value,
            name=name,
        )
    )

    candidate = normalized

    if candidate.endswith(
        "Z"
    ):
        candidate = (
            candidate[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            candidate
        )
    except ValueError as error:
        raise ValueError(
            f"{name} must be a valid timestamp."
        ) from error

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise ValueError(
            f"{name} must be timezone-aware."
        )

    return parsed.astimezone(
        timezone.utc
    )