"""
TODOBA Customer Setup Access Code Service.

Owns one opaque customer-facing access code for an already
authoritative Customer Setup Activation.

Customer-facing wording may call this an "Activation Code",
but this owner deliberately does not own setup activation
rights themselves.

Trust boundary:

    opaque customer Setup access code
        -> server-side verifier lookup
        -> authoritative setup_activation_id
        -> authoritative customer_id

Security rules:
- setup_activation_id comes from authoritative server state
- customer_id is never accepted from the code caller
- plaintext access codes are never persisted
- persisted state contains only SHA-256 code verifiers
- access codes are high-entropy opaque bearer secrets
- only ACTIVE setup activations may issue or authorize codes
- rotating a code invalidates the previous code
- explicit revocation is fail closed and durable
- no payment, billing, subscription, HTTP, deployment,
  package, MT5, or entitlement authority is owned here

Payment may later become one upstream reason to grant a Setup
Activation, but payment identity is intentionally absent from
this owner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import uuid

from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)


STORE_VERSION = 1

_CODE_PREFIX = "tdbsa"
_SECRET_BYTES = 32
_ID_GENERATION_ATTEMPTS = 32


class CustomerSetupAccessCodeStatus(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class CustomerSetupAccessCodeRecord:
    """
    Durable non-secret truth for one Setup access code.
    """

    access_code_id: str
    setup_activation_id: str
    code_sha256: str
    status: CustomerSetupAccessCodeStatus

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "access_code_id",
            "setup_activation_id",
            "code_sha256",
        ):
            object.__setattr__(
                self,
                name,
                self._normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

        if not isinstance(
            self.status,
            CustomerSetupAccessCodeStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerSetupAccessCodeStatus."
            )

        if len(self.code_sha256) != 64:
            raise ValueError(
                "code_sha256 must be a SHA-256 hex digest."
            )

        try:
            int(
                self.code_sha256,
                16,
            )
        except ValueError as exc:
            raise ValueError(
                "code_sha256 must be a SHA-256 hex digest."
            ) from exc

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
                f"{name} must not be empty."
            )

        if normalized != value:
            raise ValueError(
                f"{name} must be normalized."
            )

        return normalized


@dataclass(frozen=True)
class CustomerSetupAccessCodeIssuance:
    """
    One plaintext code returned only at issuance time.
    """

    access_code_id: str
    setup_activation_id: str
    customer_id: str
    activation_code: str = field(
        repr=False
    )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupAccessCodeIssuance("
            f"access_code_id={self.access_code_id!r}, "
            "setup_activation_id="
            f"{self.setup_activation_id!r}, "
            f"customer_id={self.customer_id!r}, "
            "activation_code=<redacted>)"
        )


@dataclass(frozen=True)
class CustomerSetupAccessCodeAuthorization:
    """
    Safe authoritative result after code verification.
    """

    setup_activation_id: str
    customer_id: str


class CustomerSetupAccessCodeStore:
    """
    Durable owner of non-secret access-code verifier state.
    """

    def __init__(
        self,
        storage_path: Path,
        *,
        setup_activation_store: CustomerSetupActivationStore,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        if not isinstance(
            setup_activation_store,
            CustomerSetupActivationStore,
        ):
            raise TypeError(
                "setup_activation_store must be "
                "CustomerSetupActivationStore."
            )

        if not setup_activation_store.is_ready():
            raise ValueError(
                "setup_activation_store must be ready."
            )

        self.storage_path = storage_path
        self._setup_activation_store = (
            setup_activation_store
        )

        self._records: dict[
            str,
            CustomerSetupAccessCodeRecord,
        ] = {}

        self._active_code_id_by_setup_activation_id: dict[
            str,
            str,
        ] = {}

        self._ready = False
        self._lock = threading.RLock()

        if self.storage_path.exists():
            self.open_existing()

    def initialize_empty(
        self,
    ) -> None:
        with self._lock:
            if self._ready:
                raise ValueError(
                    "Customer setup access code store "
                    "is already ready."
                )

            self._write_records(
                {}
            )

            self._records = {}
            self._active_code_id_by_setup_activation_id = {}
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if self._ready:
                raise ValueError(
                    "Customer setup access code store "
                    "is already ready."
                )

            if not self.storage_path.exists():
                raise FileNotFoundError(
                    self.storage_path
                )

            self._restore_from_disk()

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        record: CustomerSetupAccessCodeRecord,
    ) -> CustomerSetupAccessCodeRecord:
        if not isinstance(
            record,
            CustomerSetupAccessCodeRecord,
        ):
            raise TypeError(
                "CustomerSetupAccessCodeStore requires "
                "CustomerSetupAccessCodeRecord."
            )

        with self._lock:
            self._require_ready()
            self._require_activation_exists(
                record.setup_activation_id
            )

            existing = self._records.get(
                record.access_code_id
            )

            if existing is not None:
                if existing != record:
                    raise ValueError(
                        "Customer setup access code identity "
                        "is already bound to different state."
                    )

                return existing

            if (
                record.status
                is CustomerSetupAccessCodeStatus.ACTIVE
            ):
                existing_active_id = (
                    self
                    ._active_code_id_by_setup_activation_id
                    .get(
                        record.setup_activation_id
                    )
                )

                if existing_active_id is not None:
                    raise ValueError(
                        "Customer setup activation already "
                        "has an active access code."
                    )

            candidate = dict(
                self._records
            )
            candidate[
                record.access_code_id
            ] = record

            self._write_records(
                candidate
            )

            self._records = candidate
            self._rebuild_active_index()

            return record

    def get(
        self,
        *,
        access_code_id: str,
    ) -> CustomerSetupAccessCodeRecord | None:
        self._require_ready()

        normalized_id = (
            CustomerSetupAccessCodeRecord
            ._normalize_required_string(
                access_code_id,
                name="access_code_id",
            )
        )

        return self._records.get(
            normalized_id
        )

    def get_active_by_setup_activation_id(
        self,
        *,
        setup_activation_id: str,
    ) -> CustomerSetupAccessCodeRecord | None:
        self._require_ready()

        normalized_activation_id = (
            CustomerSetupAccessCodeRecord
            ._normalize_required_string(
                setup_activation_id,
                name="setup_activation_id",
            )
        )

        code_id = (
            self
            ._active_code_id_by_setup_activation_id
            .get(
                normalized_activation_id
            )
        )

        if code_id is None:
            return None

        return self._records[
            code_id
        ]

    def revoke(
        self,
        *,
        access_code_id: str,
    ) -> CustomerSetupAccessCodeRecord:
        with self._lock:
            self._require_ready()

            existing = self.get(
                access_code_id=access_code_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown customer setup access code."
                )

            if (
                existing.status
                is CustomerSetupAccessCodeStatus.REVOKED
            ):
                return existing

            updated = CustomerSetupAccessCodeRecord(
                access_code_id=existing.access_code_id,
                setup_activation_id=(
                    existing.setup_activation_id
                ),
                code_sha256=existing.code_sha256,
                status=(
                    CustomerSetupAccessCodeStatus.REVOKED
                ),
            )

            candidate = dict(
                self._records
            )
            candidate[
                updated.access_code_id
            ] = updated

            self._write_records(
                candidate
            )

            self._records = candidate
            self._rebuild_active_index()

            return updated

    def all(
        self,
    ) -> tuple[
        CustomerSetupAccessCodeRecord,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._records[
                code_id
            ]
            for code_id in sorted(
                self._records
            )
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer setup access code store "
                "is not initialized."
            )

    def _require_activation_exists(
        self,
        setup_activation_id: str,
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
                "Customer setup access code references "
                "an unknown setup activation."
            )

        return activation

    def _rebuild_active_index(
        self,
    ) -> None:
        active_index: dict[
            str,
            str,
        ] = {}

        for record in self._records.values():
            if (
                record.status
                is not CustomerSetupAccessCodeStatus.ACTIVE
            ):
                continue

            if (
                record.setup_activation_id
                in active_index
            ):
                raise RuntimeError(
                    "Multiple active customer setup access "
                    "codes reference one setup activation."
                )

            active_index[
                record.setup_activation_id
            ] = record.access_code_id

        self._active_code_id_by_setup_activation_id = (
            active_index
        )

    def _restore_from_disk(
        self,
    ) -> None:
        try:
            payload = json.loads(
                self.storage_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "Customer setup access code store "
                "is unreadable."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer setup access code store "
                "must contain an object."
            )

        if set(
            payload
        ) != {
            "version",
            "records",
        }:
            raise ValueError(
                "Customer setup access code store "
                "has invalid fields."
            )

        if payload[
            "version"
        ] != STORE_VERSION:
            raise ValueError(
                "Unsupported customer setup access code "
                "store version."
            )

        items = payload[
            "records"
        ]

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer setup access code records "
                "must be a list."
            )

        restored: dict[
            str,
            CustomerSetupAccessCodeRecord,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer setup access code record "
                    "must be an object."
                )

            if set(
                item
            ) != {
                "access_code_id",
                "setup_activation_id",
                "code_sha256",
                "status",
            }:
                raise ValueError(
                    "Customer setup access code record "
                    "has invalid fields."
                )

            try:
                record = CustomerSetupAccessCodeRecord(
                    access_code_id=item[
                        "access_code_id"
                    ],
                    setup_activation_id=item[
                        "setup_activation_id"
                    ],
                    code_sha256=item[
                        "code_sha256"
                    ],
                    status=(
                        CustomerSetupAccessCodeStatus(
                            item[
                                "status"
                            ]
                        )
                    ),
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Customer setup access code record "
                    "is invalid."
                ) from exc

            if (
                record.access_code_id
                in restored
            ):
                raise ValueError(
                    "Duplicate customer setup access "
                    "code identity."
                )

            self._require_activation_exists(
                record.setup_activation_id
            )

            restored[
                record.access_code_id
            ] = record

        self._records = restored

        try:
            self._rebuild_active_index()
        except RuntimeError as exc:
            raise ValueError(
                "Customer setup access code store "
                "contains conflicting active codes."
            ) from exc

        self._ready = True

    def _write_records(
        self,
        records: dict[
            str,
            CustomerSetupAccessCodeRecord,
        ],
    ) -> None:
        items = []

        for code_id in sorted(
            records
        ):
            record = records[
                code_id
            ]

            items.append(
                {
                    "access_code_id": (
                        record.access_code_id
                    ),
                    "setup_activation_id": (
                        record.setup_activation_id
                    ),
                    "code_sha256": (
                        record.code_sha256
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

        encoded = (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode(
            "utf-8"
        )

        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.storage_path.parent,
                prefix=(
                    self.storage_path.name
                    + "."
                ),
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(
                    handle.name
                )

                handle.write(
                    encoded
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
            if (
                temporary_path is not None
                and temporary_path.exists()
            ):
                temporary_path.unlink()


class CustomerSetupAccessCodeService:
    """
    Issue and verify customer-facing Setup access codes.

    This service never grants the underlying Setup Activation.
    """

    def __init__(
        self,
        *,
        access_code_store: CustomerSetupAccessCodeStore,
        setup_activation_store: CustomerSetupActivationStore,
    ) -> None:
        if not isinstance(
            access_code_store,
            CustomerSetupAccessCodeStore,
        ):
            raise TypeError(
                "access_code_store must be "
                "CustomerSetupAccessCodeStore."
            )

        if not access_code_store.is_ready():
            raise ValueError(
                "access_code_store must be ready."
            )

        if not isinstance(
            setup_activation_store,
            CustomerSetupActivationStore,
        ):
            raise TypeError(
                "setup_activation_store must be "
                "CustomerSetupActivationStore."
            )

        if not setup_activation_store.is_ready():
            raise ValueError(
                "setup_activation_store must be ready."
            )

        self._access_code_store = (
            access_code_store
        )
        self._setup_activation_store = (
            setup_activation_store
        )
        self._lock = threading.RLock()

    def issue(
        self,
        *,
        setup_activation_id: str,
    ) -> CustomerSetupAccessCodeIssuance:
        """
        Issue a fresh code for one ACTIVE Setup Activation.

        If another code is active for the same activation,
        it is durably revoked before the new code is issued.
        """

        with self._lock:
            activation = self._require_active_activation(
                setup_activation_id
            )

            existing = (
                self._access_code_store
                .get_active_by_setup_activation_id(
                    setup_activation_id=(
                        activation.setup_activation_id
                    )
                )
            )

            if existing is not None:
                self._access_code_store.revoke(
                    access_code_id=(
                        existing.access_code_id
                    )
                )

            for _ in range(
                _ID_GENERATION_ATTEMPTS
            ):
                access_code_id = (
                    uuid.uuid4().hex
                )

                if (
                    self._access_code_store.get(
                        access_code_id=(
                            access_code_id
                        )
                    )
                    is not None
                ):
                    continue

                secret = secrets.token_urlsafe(
                    _SECRET_BYTES
                )

                activation_code = (
                    f"{_CODE_PREFIX}."
                    f"{access_code_id}."
                    f"{secret}"
                )

                record = (
                    CustomerSetupAccessCodeRecord(
                        access_code_id=(
                            access_code_id
                        ),
                        setup_activation_id=(
                            activation
                            .setup_activation_id
                        ),
                        code_sha256=(
                            self._derive_code_sha256(
                                activation_code
                            )
                        ),
                        status=(
                            CustomerSetupAccessCodeStatus
                            .ACTIVE
                        ),
                    )
                )

                self._access_code_store.register(
                    record
                )

                return (
                    CustomerSetupAccessCodeIssuance(
                        access_code_id=(
                            access_code_id
                        ),
                        setup_activation_id=(
                            activation
                            .setup_activation_id
                        ),
                        customer_id=(
                            activation.customer_id
                        ),
                        activation_code=(
                            activation_code
                        ),
                    )
                )

            raise RuntimeError(
                "Unable to generate unique customer "
                "setup access code identity."
            )

    def authorize(
        self,
        *,
        activation_code: str,
    ) -> CustomerSetupAccessCodeAuthorization:
        """
        Verify one customer-supplied Activation Code.

        No customer or activation identity is accepted from
        the caller.
        """

        normalized_code = (
            self._normalize_activation_code(
                activation_code
            )
        )

        access_code_id = (
            self._parse_access_code_id(
                normalized_code
            )
        )

        record = self._access_code_store.get(
            access_code_id=(
                access_code_id
            )
        )

        if (
            record is None
            or record.status
            is not CustomerSetupAccessCodeStatus.ACTIVE
        ):
            raise ValueError(
                "Customer setup access code is invalid."
            )

        supplied_sha256 = (
            self._derive_code_sha256(
                normalized_code
            )
        )

        if not secrets.compare_digest(
            record.code_sha256,
            supplied_sha256,
        ):
            raise ValueError(
                "Customer setup access code is invalid."
            )

        activation = self._require_active_activation(
            record.setup_activation_id
        )

        return CustomerSetupAccessCodeAuthorization(
            setup_activation_id=(
                activation.setup_activation_id
            ),
            customer_id=(
                activation.customer_id
            ),
        )

    def revoke(
        self,
        *,
        access_code_id: str,
    ) -> CustomerSetupAccessCodeRecord:
        return self._access_code_store.revoke(
            access_code_id=access_code_id
        )

    def _require_active_activation(
        self,
        setup_activation_id: str,
    ):
        normalized_activation_id = (
            CustomerSetupAccessCodeRecord
            ._normalize_required_string(
                setup_activation_id,
                name="setup_activation_id",
            )
        )

        activation = (
            self._setup_activation_store.get(
                setup_activation_id=(
                    normalized_activation_id
                )
            )
        )

        if activation is None:
            raise ValueError(
                "Unknown customer setup activation."
            )

        if (
            activation.status
            is not CustomerSetupActivationStatus.ACTIVE
        ):
            raise ValueError(
                "Customer setup activation is not active."
            )

        return activation

    @staticmethod
    def _derive_code_sha256(
        activation_code: str,
    ) -> str:
        return hashlib.sha256(
            activation_code.encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _normalize_activation_code(
        activation_code: str,
    ) -> str:
        if not isinstance(
            activation_code,
            str,
        ):
            raise TypeError(
                "activation_code must be str."
            )

        normalized = activation_code.strip()

        if (
            not normalized
            or normalized != activation_code
        ):
            raise ValueError(
                "Customer setup access code is invalid."
            )

        return normalized

    @staticmethod
    def _parse_access_code_id(
        activation_code: str,
    ) -> str:
        parts = activation_code.split(
            "."
        )

        if (
            len(parts) != 3
            or parts[0] != _CODE_PREFIX
            or len(parts[1]) != 32
            or not parts[1].isalnum()
            or not parts[2]
        ):
            raise ValueError(
                "Customer setup access code is invalid."
            )

        try:
            uuid.UUID(
                hex=parts[1]
            )
        except ValueError as exc:
            raise ValueError(
                "Customer setup access code is invalid."
            ) from exc

        return parts[1]