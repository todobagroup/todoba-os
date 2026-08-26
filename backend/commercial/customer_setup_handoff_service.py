"""
TODOBA Customer Setup Handoff Service

Owns short-lived secure credentials that transfer one
authoritative customer setup right into the TODOBA Setup
installer.

Credential format:

    tdbsh1.<handoff_id>.<secret>

Durable state stores only:

- issuance_request_id
- handoff_id
- setup_activation_id
- verifier_sha256
- issued_at
- expires_at
- status

The plaintext handoff credential is returned only during
issuance and is never persisted.

Status model:

    ACTIVE
        Credential may authorize while still inside its
        expiration window and while the referenced setup
        activation is commercially eligible.

    REVOKED
        Credential can never authorize again.

Expiration is computed truth, not durable status:

    current_time >= expires_at
        -> expired

Retry contract:

- same issuance_request_id + same setup_activation_id
  keeps the same handoff_id
- plaintext secret rotates on retry
- verifier is replaced atomically
- issued_at and expires_at never move on retry
- expired handoffs cannot be revived by retry
- revoked handoffs cannot be revived by retry
- a new issuance request for the same setup activation
  atomically revokes the previous ACTIVE handoff

Commercial scope:

- ACTIVE setup activations may use handoff credentials
- BOUND setup activations may continue using handoff
  credentials for deterministic recovery / installation
- SUSPENDED setup activations fail closed

This owner deliberately does not:

- process payments or subscriptions
- create customer registrations
- create or bind setup activations
- inspect MT5 account fingerprints
- create customer deployments
- issue long-lived customer access credentials
- build or deliver deployment packages
- authorize deployment runtime entitlement
- expose HTTP routes
"""

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

from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)


STORE_VERSION = 1

_HANDOFF_PREFIX = "tdbsh1"
_HANDOFF_ID_RANDOM_BYTES = 16
_HANDOFF_SECRET_RANDOM_BYTES = 32
_HANDOFF_TTL = timedelta(
    minutes=30,
)
_GENERATION_ATTEMPTS = 128

_HANDOFF_ID_PATTERN = re.compile(
    r"^[0-9a-f]{32}$"
)

_VERIFIER_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)

_SECRET_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]+$"
)


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
        return value.replace(
            tzinfo=timezone.utc
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
        normalized.isoformat()
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
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be str."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} is required."
        )

    if normalized_value.endswith(
        "Z"
    ):
        normalized_value = (
            normalized_value[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            normalized_value
        )
    except ValueError as error:
        raise ValueError(
            f"{name} must use ISO 8601 format."
        ) from error

    return _normalize_datetime(
        parsed
    )


def _normalize_timestamp(
    value: str,
    *,
    name: str,
) -> str:
    return _serialize_timestamp(
        _parse_timestamp(
            value,
            name=name,
        )
    )


class CustomerSetupHandoffStatus(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(
    frozen=True,
)
class CustomerSetupHandoffRecord:
    """
    Immutable durable truth for one setup handoff.
    """

    issuance_request_id: str
    handoff_id: str
    setup_activation_id: str
    verifier_sha256: str
    issued_at: str
    expires_at: str
    status: CustomerSetupHandoffStatus

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "issuance_request_id",
            self._normalize_required_string(
                self.issuance_request_id,
                name="issuance_request_id",
            ),
        )

        object.__setattr__(
            self,
            "handoff_id",
            self._normalize_handoff_id(
                self.handoff_id
            ),
        )

        object.__setattr__(
            self,
            "setup_activation_id",
            self._normalize_required_string(
                self.setup_activation_id,
                name="setup_activation_id",
            ),
        )

        object.__setattr__(
            self,
            "verifier_sha256",
            self._normalize_verifier(
                self.verifier_sha256
            ),
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
            CustomerSetupHandoffStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerSetupHandoffStatus."
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

    @staticmethod
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

    @staticmethod
    def _normalize_handoff_id(
        value: str,
    ) -> str:
        normalized = (
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                value,
                name="handoff_id",
            )
        )

        if not _HANDOFF_ID_PATTERN.fullmatch(
            normalized
        ):
            raise ValueError(
                "Invalid customer setup handoff_id."
            )

        return normalized

    @staticmethod
    def _normalize_verifier(
        value: str,
    ) -> str:
        normalized = (
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                value,
                name="verifier_sha256",
            )
        ).lower()

        if not _VERIFIER_PATTERN.fullmatch(
            normalized
        ):
            raise ValueError(
                "Invalid customer setup handoff verifier."
            )

        return normalized


@dataclass(
    frozen=True,
)
class CustomerSetupHandoffIssuanceResult:
    """
    One issuance response.

    handoff_credential is intentionally excluded from repr.
    """

    issuance_request_id: str
    handoff_id: str
    setup_activation_id: str
    issued_at: str
    expires_at: str
    handoff_credential: str = field(
        repr=False,
    )

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "issuance_request_id",
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                self.issuance_request_id,
                name="issuance_request_id",
            ),
        )

        object.__setattr__(
            self,
            "handoff_id",
            CustomerSetupHandoffRecord
            ._normalize_handoff_id(
                self.handoff_id
            ),
        )

        object.__setattr__(
            self,
            "setup_activation_id",
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                self.setup_activation_id,
                name="setup_activation_id",
            ),
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
            self.handoff_credential,
            str,
        ):
            raise TypeError(
                "handoff_credential must be str."
            )

        credential = self.handoff_credential.strip()

        if not credential:
            raise ValueError(
                "handoff_credential is required."
            )

        object.__setattr__(
            self,
            "handoff_credential",
            credential,
        )


@dataclass(
    frozen=True,
)
class CustomerSetupHandoffAuthorization:
    """
    Safe authorization context returned to downstream setup
    capabilities.

    No bearer secret or verifier is exposed.
    """

    handoff_id: str
    setup_activation_id: str
    customer_id: str
    deployment_id: str | None

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "handoff_id",
            CustomerSetupHandoffRecord
            ._normalize_handoff_id(
                self.handoff_id
            ),
        )

        object.__setattr__(
            self,
            "setup_activation_id",
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                self.setup_activation_id,
                name="setup_activation_id",
            ),
        )

        object.__setattr__(
            self,
            "customer_id",
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                self.customer_id,
                name="customer_id",
            ),
        )

        if self.deployment_id is not None:
            object.__setattr__(
                self,
                "deployment_id",
                CustomerSetupHandoffRecord
                ._normalize_required_string(
                    self.deployment_id,
                    name="deployment_id",
                ),
            )


def derive_customer_setup_handoff_verifier(
    handoff_credential: str,
) -> str:
    """
    Derive durable SHA-256 verifier from one complete
    high-entropy handoff credential.
    """

    if not isinstance(
        handoff_credential,
        str,
    ):
        raise TypeError(
            "handoff_credential must be str."
        )

    normalized = handoff_credential.strip()

    if not normalized:
        raise ValueError(
            "handoff_credential is required."
        )

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


class CustomerSetupHandoffStore:
    """
    Durable owner of setup handoff credential truth.

    Primary identity:
        handoff_id

    Idempotency identity:
        issuance_request_id

    At most one durable ACTIVE handoff may exist for one
    setup_activation_id.
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

        self._records: dict[
            str,
            CustomerSetupHandoffRecord,
        ] = {}

        self._handoff_id_by_issuance_request_id: dict[
            str,
            str,
        ] = {}

        self._handoff_id_by_verifier: dict[
            str,
            str,
        ] = {}

        self._active_handoff_id_by_setup_activation_id: dict[
            str,
            str,
        ] = {}

        self._ready = False
        self._lock = threading.RLock()

        if self.storage_path.exists():
            self._restore_from_disk()

    def initialize_empty(
        self,
    ) -> None:
        with self._lock:
            if self._ready:
                return

            if self.storage_path.exists():
                self._restore_from_disk()
                return

            self._write_records(
                {}
            )

            self._records = {}
            self._handoff_id_by_issuance_request_id = {}
            self._handoff_id_by_verifier = {}
            self._active_handoff_id_by_setup_activation_id = {}
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def get(
        self,
        *,
        handoff_id: str,
    ) -> CustomerSetupHandoffRecord | None:
        self._require_ready()

        normalized_handoff_id = (
            CustomerSetupHandoffRecord
            ._normalize_handoff_id(
                handoff_id
            )
        )

        return self._records.get(
            normalized_handoff_id
        )

    def get_by_issuance_request_id(
        self,
        *,
        issuance_request_id: str,
    ) -> CustomerSetupHandoffRecord | None:
        self._require_ready()

        normalized_request_id = (
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                issuance_request_id,
                name="issuance_request_id",
            )
        )

        handoff_id = (
            self._handoff_id_by_issuance_request_id.get(
                normalized_request_id
            )
        )

        if handoff_id is None:
            return None

        return self._records[
            handoff_id
        ]

    def get_by_verifier(
        self,
        *,
        verifier_sha256: str,
    ) -> CustomerSetupHandoffRecord | None:
        self._require_ready()

        normalized_verifier = (
            CustomerSetupHandoffRecord
            ._normalize_verifier(
                verifier_sha256
            )
        )

        handoff_id = (
            self._handoff_id_by_verifier.get(
                normalized_verifier
            )
        )

        if handoff_id is None:
            return None

        return self._records[
            handoff_id
        ]

    def get_active_for_setup_activation(
        self,
        *,
        setup_activation_id: str,
    ) -> CustomerSetupHandoffRecord | None:
        self._require_ready()

        normalized_activation_id = (
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                setup_activation_id,
                name="setup_activation_id",
            )
        )

        handoff_id = (
            self
            ._active_handoff_id_by_setup_activation_id
            .get(
                normalized_activation_id
            )
        )

        if handoff_id is None:
            return None

        return self._records[
            handoff_id
        ]

    def supersede(
        self,
        record: CustomerSetupHandoffRecord,
    ) -> CustomerSetupHandoffRecord:
        """
        Atomically revoke any existing ACTIVE handoff for the
        same setup activation and install this new ACTIVE
        record.
        """

        if not isinstance(
            record,
            CustomerSetupHandoffRecord,
        ):
            raise TypeError(
                "CustomerSetupHandoffStore requires "
                "CustomerSetupHandoffRecord."
            )

        if (
            record.status
            is not CustomerSetupHandoffStatus.ACTIVE
        ):
            raise ValueError(
                "New setup handoff must start ACTIVE."
            )

        with self._lock:
            self._require_ready()

            if (
                record.handoff_id
                in self._records
            ):
                raise ValueError(
                    "Customer setup handoff_id is already "
                    "assigned."
                )

            if (
                record.issuance_request_id
                in self._handoff_id_by_issuance_request_id
            ):
                raise ValueError(
                    "Customer setup handoff issuance "
                    "request is already assigned."
                )

            if (
                record.verifier_sha256
                in self._handoff_id_by_verifier
            ):
                raise ValueError(
                    "Customer setup handoff verifier is "
                    "already assigned."
                )

            candidate = dict(
                self._records
            )

            existing_handoff_id = (
                self
                ._active_handoff_id_by_setup_activation_id
                .get(
                    record.setup_activation_id
                )
            )

            if existing_handoff_id is not None:
                existing = candidate[
                    existing_handoff_id
                ]

                candidate[
                    existing_handoff_id
                ] = CustomerSetupHandoffRecord(
                    issuance_request_id=(
                        existing.issuance_request_id
                    ),
                    handoff_id=existing.handoff_id,
                    setup_activation_id=(
                        existing.setup_activation_id
                    ),
                    verifier_sha256=(
                        existing.verifier_sha256
                    ),
                    issued_at=existing.issued_at,
                    expires_at=existing.expires_at,
                    status=(
                        CustomerSetupHandoffStatus.REVOKED
                    ),
                )

            candidate[
                record.handoff_id
            ] = record

            indexes = self._build_indexes(
                candidate
            )

            self._write_records(
                candidate
            )

            self._install_candidate(
                candidate,
                indexes,
            )

            return record

    def rotate_verifier(
        self,
        *,
        handoff_id: str,
        verifier_sha256: str,
    ) -> CustomerSetupHandoffRecord:
        """
        Rotate plaintext-secret verifier without changing
        issuance identity or lifetime.
        """

        normalized_handoff_id = (
            CustomerSetupHandoffRecord
            ._normalize_handoff_id(
                handoff_id
            )
        )

        normalized_verifier = (
            CustomerSetupHandoffRecord
            ._normalize_verifier(
                verifier_sha256
            )
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                normalized_handoff_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown customer setup handoff."
                )

            if (
                existing.status
                is CustomerSetupHandoffStatus.REVOKED
            ):
                raise ValueError(
                    "REVOKED customer setup handoff "
                    "cannot rotate verifier."
                )

            verifier_owner = (
                self._handoff_id_by_verifier.get(
                    normalized_verifier
                )
            )

            if (
                verifier_owner is not None
                and verifier_owner
                != existing.handoff_id
            ):
                raise ValueError(
                    "Customer setup handoff verifier is "
                    "already assigned."
                )

            if (
                existing.verifier_sha256
                == normalized_verifier
            ):
                return existing

            updated = CustomerSetupHandoffRecord(
                issuance_request_id=(
                    existing.issuance_request_id
                ),
                handoff_id=existing.handoff_id,
                setup_activation_id=(
                    existing.setup_activation_id
                ),
                verifier_sha256=(
                    normalized_verifier
                ),
                issued_at=existing.issued_at,
                expires_at=existing.expires_at,
                status=existing.status,
            )

            candidate = dict(
                self._records
            )

            candidate[
                existing.handoff_id
            ] = updated

            indexes = self._build_indexes(
                candidate
            )

            self._write_records(
                candidate
            )

            self._install_candidate(
                candidate,
                indexes,
            )

            return updated

    def revoke(
        self,
        *,
        handoff_id: str,
    ) -> CustomerSetupHandoffRecord:
        normalized_handoff_id = (
            CustomerSetupHandoffRecord
            ._normalize_handoff_id(
                handoff_id
            )
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                normalized_handoff_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown customer setup handoff."
                )

            if (
                existing.status
                is CustomerSetupHandoffStatus.REVOKED
            ):
                return existing

            updated = CustomerSetupHandoffRecord(
                issuance_request_id=(
                    existing.issuance_request_id
                ),
                handoff_id=existing.handoff_id,
                setup_activation_id=(
                    existing.setup_activation_id
                ),
                verifier_sha256=(
                    existing.verifier_sha256
                ),
                issued_at=existing.issued_at,
                expires_at=existing.expires_at,
                status=(
                    CustomerSetupHandoffStatus.REVOKED
                ),
            )

            candidate = dict(
                self._records
            )

            candidate[
                existing.handoff_id
            ] = updated

            indexes = self._build_indexes(
                candidate
            )

            self._write_records(
                candidate
            )

            self._install_candidate(
                candidate,
                indexes,
            )

            return updated

    def all(
        self,
    ) -> tuple[
        CustomerSetupHandoffRecord,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._records[
                handoff_id
            ]
            for handoff_id in sorted(
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

    def _build_indexes(
        self,
        records: dict[
            str,
            CustomerSetupHandoffRecord,
        ],
    ) -> tuple[
        dict[str, str],
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

        active_activation_index: dict[
            str,
            str,
        ] = {}

        for handoff_id in sorted(
            records
        ):
            record = records[
                handoff_id
            ]

            if record.handoff_id != handoff_id:
                raise ValueError(
                    "Customer setup handoff record key "
                    "is inconsistent."
                )

            if (
                record.issuance_request_id
                in request_index
            ):
                raise ValueError(
                    "Duplicate customer setup handoff "
                    "issuance request."
                )

            if (
                record.verifier_sha256
                in verifier_index
            ):
                raise ValueError(
                    "Duplicate customer setup handoff "
                    "verifier."
                )

            request_index[
                record.issuance_request_id
            ] = record.handoff_id

            verifier_index[
                record.verifier_sha256
            ] = record.handoff_id

            if (
                record.status
                is CustomerSetupHandoffStatus.ACTIVE
            ):
                if (
                    record.setup_activation_id
                    in active_activation_index
                ):
                    raise ValueError(
                        "Multiple ACTIVE customer setup "
                        "handoffs reference one setup "
                        "activation."
                    )

                active_activation_index[
                    record.setup_activation_id
                ] = record.handoff_id

        return (
            request_index,
            verifier_index,
            active_activation_index,
        )

    def _install_candidate(
        self,
        records: dict[
            str,
            CustomerSetupHandoffRecord,
        ],
        indexes: tuple[
            dict[str, str],
            dict[str, str],
            dict[str, str],
        ],
    ) -> None:
        (
            request_index,
            verifier_index,
            active_activation_index,
        ) = indexes

        self._records = records
        self._handoff_id_by_issuance_request_id = (
            request_index
        )
        self._handoff_id_by_verifier = (
            verifier_index
        )
        self._active_handoff_id_by_setup_activation_id = (
            active_activation_index
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer setup handoff store is not "
                "initialized."
            )

    def _restore_from_disk(
        self,
    ) -> None:
        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8",
            )
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer setup handoff payload must be "
                "an object."
            )

        if set(
            payload
        ) != {
            "version",
            "records",
        }:
            raise ValueError(
                "Customer setup handoff payload has "
                "invalid fields."
            )

        if payload.get(
            "version"
        ) != STORE_VERSION:
            raise ValueError(
                "Unsupported customer setup handoff "
                "store version."
            )

        items = payload.get(
            "records"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer setup handoff records must be "
                "a list."
            )

        restored: dict[
            str,
            CustomerSetupHandoffRecord,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer setup handoff item must be "
                    "an object."
                )

            if set(
                item
            ) != {
                "issuance_request_id",
                "handoff_id",
                "setup_activation_id",
                "verifier_sha256",
                "issued_at",
                "expires_at",
                "status",
            }:
                raise ValueError(
                    "Customer setup handoff item has "
                    "invalid fields."
                )

            try:
                status = CustomerSetupHandoffStatus(
                    item[
                        "status"
                    ]
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Customer setup handoff item has "
                    "invalid status."
                ) from error

            record = CustomerSetupHandoffRecord(
                issuance_request_id=item[
                    "issuance_request_id"
                ],
                handoff_id=item[
                    "handoff_id"
                ],
                setup_activation_id=item[
                    "setup_activation_id"
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
                status=status,
            )

            if (
                record.handoff_id
                in restored
            ):
                raise ValueError(
                    "Duplicate customer setup handoff_id."
                )

            restored[
                record.handoff_id
            ] = record

        indexes = self._build_indexes(
            restored
        )

        self._install_candidate(
            restored,
            indexes,
        )

        self._ready = True

    def _write_records(
        self,
        records: dict[
            str,
            CustomerSetupHandoffRecord,
        ],
    ) -> None:
        items = []

        for handoff_id in sorted(
            records
        ):
            record = records[
                handoff_id
            ]

            items.append(
                {
                    "issuance_request_id": (
                        record.issuance_request_id
                    ),
                    "handoff_id": (
                        record.handoff_id
                    ),
                    "setup_activation_id": (
                        record.setup_activation_id
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
                f"{self.storage_path.name}.tmp"
            )
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file_handle:
                json.dump(
                    payload,
                    file_handle,
                    indent=2,
                    sort_keys=True,
                )

                file_handle.write(
                    "\n"
                )

                file_handle.flush()

                os.fsync(
                    file_handle.fileno()
                )

            os.replace(
                temporary_path,
                self.storage_path,
            )
        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()

            raise


class CustomerSetupHandoffService:
    """
    Issue, rotate, revoke, and authorize short-lived setup
    handoff credentials.
    """

    def __init__(
        self,
        *,
        handoff_store: CustomerSetupHandoffStore,
        setup_activation_store: CustomerSetupActivationStore,
    ) -> None:
        if not isinstance(
            handoff_store,
            CustomerSetupHandoffStore,
        ):
            raise TypeError(
                "handoff_store must be "
                "CustomerSetupHandoffStore."
            )

        if not isinstance(
            setup_activation_store,
            CustomerSetupActivationStore,
        ):
            raise TypeError(
                "setup_activation_store must be "
                "CustomerSetupActivationStore."
            )

        if not handoff_store.is_ready():
            raise RuntimeError(
                "Customer setup handoff store is not "
                "initialized."
            )

        if not setup_activation_store.is_ready():
            raise RuntimeError(
                "Customer setup activation store is not "
                "initialized."
            )

        self._handoff_store = handoff_store
        self._setup_activation_store = (
            setup_activation_store
        )
        self._lock = threading.RLock()

        self._validate_authoritative_state()

    def issue(
        self,
        *,
        issuance_request_id: str,
        setup_activation_id: str,
        current_time: datetime,
    ) -> CustomerSetupHandoffIssuanceResult:
        """
        Issue or recover one setup handoff credential.

        Existing request retry:
        - same handoff_id
        - rotated plaintext secret
        - rotated verifier
        - unchanged issued_at
        - unchanged expires_at

        Retry never revives REVOKED or expired credentials.
        """

        normalized_request_id = (
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                issuance_request_id,
                name="issuance_request_id",
            )
        )

        normalized_activation_id = (
            CustomerSetupHandoffRecord
            ._normalize_required_string(
                setup_activation_id,
                name="setup_activation_id",
            )
        )

        normalized_current_time = (
            _normalize_datetime(
                current_time
            )
        )

        with self._lock:
            self._require_sources_ready()

            self._require_setup_activation_eligible(
                setup_activation_id=(
                    normalized_activation_id
                ),
                unknown_is_runtime_error=False,
            )

            existing = (
                self._handoff_store
                .get_by_issuance_request_id(
                    issuance_request_id=(
                        normalized_request_id
                    )
                )
            )

            if existing is not None:
                if (
                    existing.setup_activation_id
                    != normalized_activation_id
                ):
                    raise ValueError(
                        "Customer setup handoff issuance "
                        "request belongs to a different "
                        "setup activation."
                    )

                if (
                    existing.status
                    is CustomerSetupHandoffStatus.REVOKED
                ):
                    raise ValueError(
                        "REVOKED customer setup handoff "
                        "cannot be reissued."
                    )

                if self._is_expired(
                    existing,
                    normalized_current_time,
                ):
                    raise ValueError(
                        "Expired customer setup handoff "
                        "cannot be reissued."
                    )

                return self._rotate_existing_secret(
                    existing
                )

            return self._issue_new(
                issuance_request_id=(
                    normalized_request_id
                ),
                setup_activation_id=(
                    normalized_activation_id
                ),
                current_time=(
                    normalized_current_time
                ),
            )

    def authorize(
        self,
        *,
        handoff_credential: str,
        current_time: datetime,
    ) -> CustomerSetupHandoffAuthorization:
        """
        Validate one supplied handoff credential without
        mutating durable state.
        """

        normalized_current_time = (
            _normalize_datetime(
                current_time
            )
        )

        with self._lock:
            self._require_sources_ready()

            (
                normalized_credential,
                handoff_id,
            ) = self._parse_credential(
                handoff_credential
            )

            record = self._handoff_store.get(
                handoff_id=handoff_id
            )

            if record is None:
                raise ValueError(
                    "Invalid customer setup handoff "
                    "credential."
                )

            supplied_verifier = (
                derive_customer_setup_handoff_verifier(
                    normalized_credential
                )
            )

            verifier_matches = compare_digest(
                supplied_verifier,
                record.verifier_sha256,
            )

            if not verifier_matches:
                raise ValueError(
                    "Invalid customer setup handoff "
                    "credential."
                )

            if (
                record.status
                is CustomerSetupHandoffStatus.REVOKED
            ):
                raise ValueError(
                    "Customer setup handoff credential "
                    "is revoked."
                )

            if self._is_expired(
                record,
                normalized_current_time,
            ):
                raise ValueError(
                    "Customer setup handoff credential "
                    "is expired."
                )

            activation = (
                self._require_setup_activation_eligible(
                    setup_activation_id=(
                        record.setup_activation_id
                    ),
                    unknown_is_runtime_error=True,
                )
            )

            return CustomerSetupHandoffAuthorization(
                handoff_id=record.handoff_id,
                setup_activation_id=(
                    record.setup_activation_id
                ),
                customer_id=(
                    activation.customer_id
                ),
                deployment_id=(
                    activation.deployment_id
                ),
            )

    def revoke(
        self,
        *,
        handoff_id: str,
    ) -> CustomerSetupHandoffRecord:
        """
        Permanently revoke one handoff credential.
        """

        with self._lock:
            self._require_sources_ready()

            return self._handoff_store.revoke(
                handoff_id=handoff_id
            )

    def get(
        self,
        *,
        handoff_id: str,
    ) -> CustomerSetupHandoffRecord | None:
        self._require_sources_ready()

        return self._handoff_store.get(
            handoff_id=handoff_id
        )

    def _issue_new(
        self,
        *,
        issuance_request_id: str,
        setup_activation_id: str,
        current_time: datetime,
    ) -> CustomerSetupHandoffIssuanceResult:
        issued_at = _serialize_timestamp(
            current_time
        )

        expires_at = _serialize_timestamp(
            current_time
            + _HANDOFF_TTL
        )

        for _ in range(
            _GENERATION_ATTEMPTS
        ):
            handoff_id = secrets.token_hex(
                _HANDOFF_ID_RANDOM_BYTES
            )

            if (
                self._handoff_store.get(
                    handoff_id=handoff_id
                )
                is not None
            ):
                continue

            handoff_credential = (
                self._generate_credential(
                    handoff_id=handoff_id
                )
            )

            verifier = (
                derive_customer_setup_handoff_verifier(
                    handoff_credential
                )
            )

            if (
                self._handoff_store.get_by_verifier(
                    verifier_sha256=verifier
                )
                is not None
            ):
                continue

            record = CustomerSetupHandoffRecord(
                issuance_request_id=(
                    issuance_request_id
                ),
                handoff_id=handoff_id,
                setup_activation_id=(
                    setup_activation_id
                ),
                verifier_sha256=verifier,
                issued_at=issued_at,
                expires_at=expires_at,
                status=(
                    CustomerSetupHandoffStatus.ACTIVE
                ),
            )

            persisted = (
                self._handoff_store.supersede(
                    record
                )
            )

            return self._build_issuance_result(
                record=persisted,
                handoff_credential=(
                    handoff_credential
                ),
            )

        raise RuntimeError(
            "Unable to generate unique customer setup "
            "handoff credential."
        )

    def _rotate_existing_secret(
        self,
        record: CustomerSetupHandoffRecord,
    ) -> CustomerSetupHandoffIssuanceResult:
        for _ in range(
            _GENERATION_ATTEMPTS
        ):
            handoff_credential = (
                self._generate_credential(
                    handoff_id=(
                        record.handoff_id
                    )
                )
            )

            verifier = (
                derive_customer_setup_handoff_verifier(
                    handoff_credential
                )
            )

            verifier_owner = (
                self._handoff_store
                .get_by_verifier(
                    verifier_sha256=verifier
                )
            )

            if (
                verifier_owner is not None
                and verifier_owner.handoff_id
                != record.handoff_id
            ):
                continue

            updated = (
                self._handoff_store.rotate_verifier(
                    handoff_id=record.handoff_id,
                    verifier_sha256=verifier,
                )
            )

            return self._build_issuance_result(
                record=updated,
                handoff_credential=(
                    handoff_credential
                ),
            )

        raise RuntimeError(
            "Unable to rotate customer setup handoff "
            "credential."
        )

    @staticmethod
    def _generate_credential(
        *,
        handoff_id: str,
    ) -> str:
        secret = secrets.token_urlsafe(
            _HANDOFF_SECRET_RANDOM_BYTES
        )

        return (
            f"{_HANDOFF_PREFIX}."
            f"{handoff_id}."
            f"{secret}"
        )

    @staticmethod
    def _parse_credential(
        handoff_credential: str,
    ) -> tuple[
        str,
        str,
    ]:
        if not isinstance(
            handoff_credential,
            str,
        ):
            raise TypeError(
                "handoff_credential must be str."
            )

        normalized = handoff_credential.strip()

        if not normalized:
            raise ValueError(
                "Invalid customer setup handoff "
                "credential."
            )

        parts = normalized.split(
            "."
        )

        if len(
            parts
        ) != 3:
            raise ValueError(
                "Invalid customer setup handoff "
                "credential."
            )

        prefix, handoff_id, secret = parts

        if prefix != _HANDOFF_PREFIX:
            raise ValueError(
                "Invalid customer setup handoff "
                "credential."
            )

        try:
            normalized_handoff_id = (
                CustomerSetupHandoffRecord
                ._normalize_handoff_id(
                    handoff_id
                )
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "Invalid customer setup handoff "
                "credential."
            ) from error

        if (
            len(
                secret
            )
            < 32
            or not _SECRET_PATTERN.fullmatch(
                secret
            )
        ):
            raise ValueError(
                "Invalid customer setup handoff "
                "credential."
            )

        return (
            normalized,
            normalized_handoff_id,
        )

    def _require_setup_activation_eligible(
        self,
        *,
        setup_activation_id: str,
        unknown_is_runtime_error: bool,
    ):
        activation = (
            self._setup_activation_store.get(
                setup_activation_id=(
                    setup_activation_id
                )
            )
        )

        if activation is None:
            if unknown_is_runtime_error:
                raise RuntimeError(
                    "Customer setup handoff references "
                    "an unknown setup activation."
                )

            raise ValueError(
                "Unknown customer setup activation."
            )

        if (
            activation.status
            is CustomerSetupActivationStatus.SUSPENDED
        ):
            raise ValueError(
                "Customer setup activation is "
                "SUSPENDED."
            )

        if (
            activation.status
            not in {
                CustomerSetupActivationStatus.ACTIVE,
                CustomerSetupActivationStatus.BOUND,
            }
        ):
            raise RuntimeError(
                "Unsupported customer setup activation "
                "status."
            )

        return activation

    @staticmethod
    def _is_expired(
        record: CustomerSetupHandoffRecord,
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

    def _validate_authoritative_state(
        self,
    ) -> None:
        for record in (
            self._handoff_store.all()
        ):
            activation = (
                self._setup_activation_store.get(
                    setup_activation_id=(
                        record.setup_activation_id
                    )
                )
            )

            if activation is None:
                raise RuntimeError(
                    "Customer setup handoff references "
                    "an unknown setup activation."
                )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._handoff_store.is_ready():
            raise RuntimeError(
                "Customer setup handoff store is not "
                "initialized."
            )

        if not self._setup_activation_store.is_ready():
            raise RuntimeError(
                "Customer setup activation store is not "
                "initialized."
            )

    @staticmethod
    def _build_issuance_result(
        *,
        record: CustomerSetupHandoffRecord,
        handoff_credential: str,
    ) -> CustomerSetupHandoffIssuanceResult:
        return CustomerSetupHandoffIssuanceResult(
            issuance_request_id=(
                record.issuance_request_id
            ),
            handoff_id=record.handoff_id,
            setup_activation_id=(
                record.setup_activation_id
            ),
            issued_at=record.issued_at,
            expires_at=record.expires_at,
            handoff_credential=(
                handoff_credential
            ),
        )