"""
Durable one-time authorization core for customer Setup bootstrap.

Authority boundary:

    trusted customer_id
    + PKCE S256 code_challenge
        -> short-lived authorization_code
        -> authorization_code + code_verifier
        -> ACTIVE -> CONSUMED
        -> authoritative CustomerIdentity

Security rules:
- authorization codes are high-entropy opaque secrets
- plaintext authorization codes are never persisted
- durable state stores only SHA-256 authorization-code verifiers
- PKCE uses S256 only
- PKCE code_verifier is never persisted
- authorization codes are short-lived
- successful redemption consumes the code atomically
- consumed authorization codes can never become ACTIVE again
- unknown or removed customer identities fail closed

This component does not:
- expose HTTP
- open browsers
- parse cookies or sessions
- read command-line arguments or environment variables
- issue downstream setup credentials
- provision deployments
- interact with MetaTrader
"""

from __future__ import annotations

from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from hmac import compare_digest
import json
import os
from pathlib import Path
import re
import secrets
import threading

from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)


_STORE_VERSION = 1

_AUTHORIZATION_PREFIX = "tdbba"
_AUTHORIZATION_ID_PATTERN = re.compile(
    r"^[0-9a-f]{32}$"
)
_AUTHORIZATION_VERIFIER_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)

_PKCE_CODE_VERIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9\-._~]{43,128}$"
)
_PKCE_S256_CHALLENGE_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{43}$"
)

_AUTHORIZATION_SECRET_RANDOM_BYTES = 32
_AUTHORIZATION_TTL = timedelta(
    minutes=5
)
_GENERATION_ATTEMPTS = 32


class CustomerSetupBootstrapAuthorizationStatus(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"


@dataclass(
    frozen=True,
    slots=True,
)
class CustomerSetupBootstrapAuthorizationRecord:
    authorization_request_id: str
    authorization_id: str
    customer_id: str
    authorization_verifier_sha256: str
    code_challenge_s256: str
    issued_at: str
    expires_at: str
    status: CustomerSetupBootstrapAuthorizationStatus
    consumed_at: str | None = None

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "authorization_request_id",
            _normalize_required_string(
                self.authorization_request_id,
                name="authorization_request_id",
            ),
        )

        object.__setattr__(
            self,
            "authorization_id",
            _normalize_authorization_id(
                self.authorization_id
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
            "authorization_verifier_sha256",
            _normalize_authorization_verifier(
                self.authorization_verifier_sha256
            ),
        )

        object.__setattr__(
            self,
            "code_challenge_s256",
            _normalize_code_challenge(
                self.code_challenge_s256
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
                "Bootstrap authorization expiry "
                "must be after issuance."
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

        status = self.status

        if not isinstance(
            status,
            CustomerSetupBootstrapAuthorizationStatus,
        ):
            try:
                status = (
                    CustomerSetupBootstrapAuthorizationStatus(
                        status
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Invalid bootstrap authorization status."
                ) from error

            object.__setattr__(
                self,
                "status",
                status,
            )

        if (
            status
            is CustomerSetupBootstrapAuthorizationStatus.ACTIVE
        ):
            if self.consumed_at is not None:
                raise ValueError(
                    "ACTIVE bootstrap authorization "
                    "cannot have consumed_at."
                )

            return

        if self.consumed_at is None:
            raise ValueError(
                "CONSUMED bootstrap authorization "
                "requires consumed_at."
            )

        consumed_at = _parse_timestamp(
            self.consumed_at,
            name="consumed_at",
        )

        if consumed_at < issued_at:
            raise ValueError(
                "Bootstrap authorization cannot be "
                "consumed before issuance."
            )

        object.__setattr__(
            self,
            "consumed_at",
            _serialize_timestamp(
                consumed_at
            ),
        )


@dataclass(
    frozen=True,
    slots=True,
)
class CustomerSetupBootstrapAuthorizationIssuance:
    authorization_request_id: str
    authorization_id: str
    customer_id: str
    issued_at: str
    expires_at: str
    authorization_code: str = field(
        repr=False
    )

    def __repr__(
        self,
    ) -> str:
        return (
            f"{type(self).__name__}("
            f"authorization_request_id="
            f"{self.authorization_request_id!r}, "
            f"authorization_id="
            f"{self.authorization_id!r}, "
            f"customer_id="
            f"{self.customer_id!r}, "
            f"issued_at={self.issued_at!r}, "
            f"expires_at={self.expires_at!r}, "
            "authorization_code=<redacted>)"
        )


@dataclass(
    frozen=True,
    slots=True,
)
class CustomerSetupBootstrapAuthorizationRedemption:
    authorization_id: str
    customer_id: str
    consumed_at: str
    customer_identity: CustomerIdentity


def derive_customer_setup_bootstrap_authorization_verifier(
    authorization_code: str,
) -> str:
    normalized = _normalize_required_string(
        authorization_code,
        name="authorization_code",
    )

    return sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


def derive_pkce_s256_code_challenge(
    code_verifier: str,
) -> str:
    normalized = _normalize_code_verifier(
        code_verifier
    )

    digest = sha256(
        normalized.encode(
            "ascii"
        )
    ).digest()

    return (
        urlsafe_b64encode(
            digest
        )
        .rstrip(
            b"="
        )
        .decode(
            "ascii"
        )
    )


class CustomerSetupBootstrapAuthorizationStore:
    """
    Durable authoritative owner of bootstrap authorization records.
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

        self.storage_path = storage_path
        self.customer_identity_registry = (
            customer_identity_registry
        )

        self._records: dict[
            str,
            CustomerSetupBootstrapAuthorizationRecord,
        ] = {}

        self._authorization_id_by_request_id: dict[
            str,
            str,
        ] = {}

        self._authorization_id_by_verifier: dict[
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

            self._require_identity_registry_ready()

            if self.storage_path.exists():
                raise FileExistsError(
                    "Bootstrap authorization store "
                    "already exists."
                )

            self._write_records(
                {}
            )

            self._records = {}
            self._authorization_id_by_request_id = {}
            self._authorization_id_by_verifier = {}
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if self._ready:
                return

            self._require_identity_registry_ready()

            if not self.storage_path.is_file():
                raise FileNotFoundError(
                    "Bootstrap authorization store "
                    "does not exist."
                )

            (
                records,
                request_index,
                verifier_index,
            ) = self._read_records()

            self._records = records
            self._authorization_id_by_request_id = (
                request_index
            )
            self._authorization_id_by_verifier = (
                verifier_index
            )
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def get(
        self,
        *,
        authorization_id: str,
    ) -> (
        CustomerSetupBootstrapAuthorizationRecord
        | None
    ):
        with self._lock:
            self._require_ready()

            normalized_id = (
                _normalize_authorization_id(
                    authorization_id
                )
            )

            return self._records.get(
                normalized_id
            )

    def get_by_request_id(
        self,
        *,
        authorization_request_id: str,
    ) -> (
        CustomerSetupBootstrapAuthorizationRecord
        | None
    ):
        with self._lock:
            self._require_ready()

            normalized_request_id = (
                _normalize_required_string(
                    authorization_request_id,
                    name=(
                        "authorization_request_id"
                    ),
                )
            )

            authorization_id = (
                self
                ._authorization_id_by_request_id
                .get(
                    normalized_request_id
                )
            )

            if authorization_id is None:
                return None

            return self._records[
                authorization_id
            ]

    def get_by_verifier(
        self,
        *,
        authorization_verifier_sha256: str,
    ) -> (
        CustomerSetupBootstrapAuthorizationRecord
        | None
    ):
        with self._lock:
            self._require_ready()

            normalized_verifier = (
                _normalize_authorization_verifier(
                    authorization_verifier_sha256
                )
            )

            authorization_id = (
                self
                ._authorization_id_by_verifier
                .get(
                    normalized_verifier
                )
            )

            if authorization_id is None:
                return None

            return self._records[
                authorization_id
            ]

    def insert(
        self,
        record: CustomerSetupBootstrapAuthorizationRecord,
    ) -> CustomerSetupBootstrapAuthorizationRecord:
        if not isinstance(
            record,
            CustomerSetupBootstrapAuthorizationRecord,
        ):
            raise TypeError(
                "record must be "
                "CustomerSetupBootstrapAuthorizationRecord."
            )

        with self._lock:
            self._require_ready()

            if (
                record.authorization_id
                in self._records
            ):
                raise ValueError(
                    "Duplicate bootstrap authorization id."
                )

            if (
                record.authorization_request_id
                in self
                ._authorization_id_by_request_id
            ):
                raise ValueError(
                    "Duplicate bootstrap authorization "
                    "request id."
                )

            if (
                record.authorization_verifier_sha256
                in self
                ._authorization_id_by_verifier
            ):
                raise ValueError(
                    "Duplicate bootstrap authorization "
                    "verifier."
                )

            self._require_record_customer_exists(
                record
            )

            candidate = dict(
                self._records
            )
            candidate[
                record.authorization_id
            ] = record

            self._write_records(
                candidate
            )

            self._install_records(
                candidate
            )

            return record

    def rotate_authorization_verifier(
        self,
        *,
        authorization_id: str,
        authorization_verifier_sha256: str,
    ) -> CustomerSetupBootstrapAuthorizationRecord:
        with self._lock:
            self._require_ready()

            normalized_id = (
                _normalize_authorization_id(
                    authorization_id
                )
            )
            normalized_verifier = (
                _normalize_authorization_verifier(
                    authorization_verifier_sha256
                )
            )

            existing = self._records.get(
                normalized_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown bootstrap authorization."
                )

            if (
                existing.status
                is not
                CustomerSetupBootstrapAuthorizationStatus.ACTIVE
            ):
                raise ValueError(
                    "Consumed bootstrap authorization "
                    "cannot rotate."
                )

            verifier_owner = (
                self
                ._authorization_id_by_verifier
                .get(
                    normalized_verifier
                )
            )

            if (
                verifier_owner is not None
                and verifier_owner
                != normalized_id
            ):
                raise ValueError(
                    "Bootstrap authorization verifier "
                    "already exists."
                )

            updated = (
                CustomerSetupBootstrapAuthorizationRecord(
                    authorization_request_id=(
                        existing.authorization_request_id
                    ),
                    authorization_id=(
                        existing.authorization_id
                    ),
                    customer_id=(
                        existing.customer_id
                    ),
                    authorization_verifier_sha256=(
                        normalized_verifier
                    ),
                    code_challenge_s256=(
                        existing.code_challenge_s256
                    ),
                    issued_at=(
                        existing.issued_at
                    ),
                    expires_at=(
                        existing.expires_at
                    ),
                    status=(
                        existing.status
                    ),
                )
            )

            candidate = dict(
                self._records
            )
            candidate[
                normalized_id
            ] = updated

            self._write_records(
                candidate
            )

            self._install_records(
                candidate
            )

            return updated

    def consume(
        self,
        *,
        authorization_id: str,
        consumed_at: datetime,
    ) -> CustomerSetupBootstrapAuthorizationRecord:
        normalized_consumed_at = (
            _normalize_datetime(
                consumed_at
            )
        )

        with self._lock:
            self._require_ready()

            normalized_id = (
                _normalize_authorization_id(
                    authorization_id
                )
            )

            existing = self._records.get(
                normalized_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown bootstrap authorization."
                )

            if (
                existing.status
                is not
                CustomerSetupBootstrapAuthorizationStatus.ACTIVE
            ):
                raise ValueError(
                    "Bootstrap authorization "
                    "is already consumed."
                )

            updated = (
                CustomerSetupBootstrapAuthorizationRecord(
                    authorization_request_id=(
                        existing.authorization_request_id
                    ),
                    authorization_id=(
                        existing.authorization_id
                    ),
                    customer_id=(
                        existing.customer_id
                    ),
                    authorization_verifier_sha256=(
                        existing
                        .authorization_verifier_sha256
                    ),
                    code_challenge_s256=(
                        existing.code_challenge_s256
                    ),
                    issued_at=(
                        existing.issued_at
                    ),
                    expires_at=(
                        existing.expires_at
                    ),
                    status=(
                        CustomerSetupBootstrapAuthorizationStatus
                        .CONSUMED
                    ),
                    consumed_at=(
                        _serialize_timestamp(
                            normalized_consumed_at
                        )
                    ),
                )
            )

            candidate = dict(
                self._records
            )
            candidate[
                normalized_id
            ] = updated

            self._write_records(
                candidate
            )

            self._install_records(
                candidate
            )

            return updated

    def _require_identity_registry_ready(
        self,
    ) -> None:
        if not (
            self.customer_identity_registry
            .is_ready()
        ):
            raise RuntimeError(
                "Customer identity registry "
                "is not ready."
            )

    def _require_record_customer_exists(
        self,
        record: CustomerSetupBootstrapAuthorizationRecord,
    ) -> None:
        identity = (
            self.customer_identity_registry.get(
                customer_id=record.customer_id
            )
        )

        if identity is None:
            raise ValueError(
                "Unknown customer identity."
            )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Bootstrap authorization store "
                "is not ready."
            )

        self._require_identity_registry_ready()

    def _install_records(
        self,
        records: dict[
            str,
            CustomerSetupBootstrapAuthorizationRecord,
        ],
    ) -> None:
        request_index: dict[
            str,
            str,
        ] = {}
        verifier_index: dict[
            str,
            str,
        ] = {}

        for record in records.values():
            if (
                record.authorization_request_id
                in request_index
            ):
                raise ValueError(
                    "Duplicate bootstrap authorization "
                    "request id."
                )

            if (
                record.authorization_verifier_sha256
                in verifier_index
            ):
                raise ValueError(
                    "Duplicate bootstrap authorization "
                    "verifier."
                )

            request_index[
                record.authorization_request_id
            ] = record.authorization_id

            verifier_index[
                record.authorization_verifier_sha256
            ] = record.authorization_id

        self._records = records
        self._authorization_id_by_request_id = (
            request_index
        )
        self._authorization_id_by_verifier = (
            verifier_index
        )

    def _read_records(
        self,
    ) -> tuple[
        dict[
            str,
            CustomerSetupBootstrapAuthorizationRecord,
        ],
        dict[str, str],
        dict[str, str],
    ]:
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
        ) as error:
            raise ValueError(
                "Invalid bootstrap authorization store."
            ) from error

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Invalid bootstrap authorization store."
            )

        if set(
            payload
        ) != {
            "version",
            "items",
        }:
            raise ValueError(
                "Invalid bootstrap authorization "
                "store fields."
            )

        if (
            payload[
                "version"
            ]
            != _STORE_VERSION
        ):
            raise ValueError(
                "Unsupported bootstrap authorization "
                "store version."
            )

        items = payload[
            "items"
        ]

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Invalid bootstrap authorization "
                "store items."
            )

        restored: dict[
            str,
            CustomerSetupBootstrapAuthorizationRecord,
        ] = {}

        request_index: dict[
            str,
            str,
        ] = {}

        verifier_index: dict[
            str,
            str,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Invalid bootstrap authorization item."
                )

            allowed_fields = {
                "authorization_request_id",
                "authorization_id",
                "customer_id",
                "authorization_verifier_sha256",
                "code_challenge_s256",
                "issued_at",
                "expires_at",
                "status",
                "consumed_at",
            }

            if (
                set(
                    item
                )
                != allowed_fields
            ):
                raise ValueError(
                    "Bootstrap authorization item "
                    "has invalid fields."
                )

            record = (
                CustomerSetupBootstrapAuthorizationRecord(
                    authorization_request_id=(
                        item[
                            "authorization_request_id"
                        ]
                    ),
                    authorization_id=(
                        item[
                            "authorization_id"
                        ]
                    ),
                    customer_id=(
                        item[
                            "customer_id"
                        ]
                    ),
                    authorization_verifier_sha256=(
                        item[
                            "authorization_verifier_sha256"
                        ]
                    ),
                    code_challenge_s256=(
                        item[
                            "code_challenge_s256"
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
                    status=(
                        item[
                            "status"
                        ]
                    ),
                    consumed_at=(
                        item[
                            "consumed_at"
                        ]
                    ),
                )
            )

            self._require_record_customer_exists(
                record
            )

            if (
                record.authorization_id
                in restored
            ):
                raise ValueError(
                    "Duplicate bootstrap authorization id."
                )

            if (
                record.authorization_request_id
                in request_index
            ):
                raise ValueError(
                    "Duplicate bootstrap authorization "
                    "request id."
                )

            if (
                record.authorization_verifier_sha256
                in verifier_index
            ):
                raise ValueError(
                    "Duplicate bootstrap authorization "
                    "verifier."
                )

            restored[
                record.authorization_id
            ] = record

            request_index[
                record.authorization_request_id
            ] = record.authorization_id

            verifier_index[
                record.authorization_verifier_sha256
            ] = record.authorization_id

        return (
            restored,
            request_index,
            verifier_index,
        )

    def _write_records(
        self,
        records: dict[
            str,
            CustomerSetupBootstrapAuthorizationRecord,
        ],
    ) -> None:
        items = []

        for authorization_id in sorted(
            records
        ):
            record = records[
                authorization_id
            ]

            items.append(
                {
                    "authorization_request_id": (
                        record.authorization_request_id
                    ),
                    "authorization_id": (
                        record.authorization_id
                    ),
                    "customer_id": (
                        record.customer_id
                    ),
                    "authorization_verifier_sha256": (
                        record
                        .authorization_verifier_sha256
                    ),
                    "code_challenge_s256": (
                        record.code_challenge_s256
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
                    "consumed_at": (
                        record.consumed_at
                    ),
                }
            )

        payload = {
            "version": _STORE_VERSION,
            "items": items,
        }

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.storage_path.with_name(
                f".{self.storage_path.name}."
                f"{secrets.token_hex(8)}.tmp"
            )
        )

        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

        try:
            with temporary_path.open(
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
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass


class CustomerSetupBootstrapAuthorizationService:
    """
    Issue and redeem one-time PKCE bootstrap authorizations.
    """

    def __init__(
        self,
        *,
        authorization_store: CustomerSetupBootstrapAuthorizationStore,
        customer_identity_registry: CustomerIdentityRegistry,
    ) -> None:
        if not isinstance(
            authorization_store,
            CustomerSetupBootstrapAuthorizationStore,
        ):
            raise TypeError(
                "authorization_store must be "
                "CustomerSetupBootstrapAuthorizationStore."
            )

        if not isinstance(
            customer_identity_registry,
            CustomerIdentityRegistry,
        ):
            raise TypeError(
                "customer_identity_registry must be "
                "CustomerIdentityRegistry."
            )

        if (
            authorization_store
            .customer_identity_registry
            is not customer_identity_registry
        ):
            raise ValueError(
                "Bootstrap authorization sources "
                "must share one customer identity registry."
            )

        self._authorization_store = (
            authorization_store
        )
        self._customer_identity_registry = (
            customer_identity_registry
        )
        self._lock = threading.RLock()

    def issue(
        self,
        *,
        authorization_request_id: str,
        customer_id: str,
        code_challenge_s256: str,
        current_time: datetime,
    ) -> CustomerSetupBootstrapAuthorizationIssuance:
        normalized_request_id = (
            _normalize_required_string(
                authorization_request_id,
                name="authorization_request_id",
            )
        )
        normalized_customer_id = (
            _normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )
        normalized_challenge = (
            _normalize_code_challenge(
                code_challenge_s256
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
                    "Unknown customer identity."
                )

            existing = (
                self._authorization_store
                .get_by_request_id(
                    authorization_request_id=(
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
                        "Bootstrap authorization request "
                        "belongs to another customer."
                    )

                if (
                    existing.code_challenge_s256
                    != normalized_challenge
                ):
                    raise ValueError(
                        "Bootstrap authorization request "
                        "has another PKCE challenge."
                    )

                if (
                    existing.status
                    is
                    CustomerSetupBootstrapAuthorizationStatus
                    .CONSUMED
                ):
                    raise ValueError(
                        "Consumed bootstrap authorization "
                        "cannot be reissued."
                    )

                if self._is_expired(
                    existing,
                    normalized_current_time,
                ):
                    raise ValueError(
                        "Expired bootstrap authorization "
                        "cannot be reissued."
                    )

                return self._rotate_existing_code(
                    existing
                )

            return self._issue_new(
                authorization_request_id=(
                    normalized_request_id
                ),
                customer_id=(
                    normalized_customer_id
                ),
                code_challenge_s256=(
                    normalized_challenge
                ),
                current_time=(
                    normalized_current_time
                ),
            )

    def redeem(
        self,
        *,
        authorization_code: str,
        code_verifier: str,
        current_time: datetime,
    ) -> CustomerSetupBootstrapAuthorizationRedemption:
        (
            normalized_code,
            authorization_id,
        ) = self._parse_authorization_code(
            authorization_code
        )

        normalized_code_verifier = (
            _normalize_code_verifier(
                code_verifier
            )
        )

        normalized_current_time = (
            _normalize_datetime(
                current_time
            )
        )

        with self._lock:
            self._require_sources_ready()

            record = (
                self._authorization_store.get(
                    authorization_id=(
                        authorization_id
                    )
                )
            )

            if record is None:
                raise ValueError(
                    "Invalid bootstrap authorization."
                )

            supplied_authorization_verifier = (
                derive_customer_setup_bootstrap_authorization_verifier(
                    normalized_code
                )
            )

            if not compare_digest(
                supplied_authorization_verifier,
                record.authorization_verifier_sha256,
            ):
                raise ValueError(
                    "Invalid bootstrap authorization."
                )

            if (
                record.status
                is
                CustomerSetupBootstrapAuthorizationStatus
                .CONSUMED
            ):
                raise ValueError(
                    "Bootstrap authorization "
                    "is already consumed."
                )

            if self._is_expired(
                record,
                normalized_current_time,
            ):
                raise ValueError(
                    "Bootstrap authorization "
                    "is expired."
                )

            supplied_challenge = (
                derive_pkce_s256_code_challenge(
                    normalized_code_verifier
                )
            )

            if not compare_digest(
                supplied_challenge,
                record.code_challenge_s256,
            ):
                raise ValueError(
                    "Invalid PKCE verifier."
                )

            identity = (
                self._customer_identity_registry.get(
                    customer_id=(
                        record.customer_id
                    )
                )
            )

            if identity is None:
                raise ValueError(
                    "Unknown customer identity."
                )

            consumed = (
                self._authorization_store.consume(
                    authorization_id=(
                        record.authorization_id
                    ),
                    consumed_at=(
                        normalized_current_time
                    ),
                )
            )

            return (
                CustomerSetupBootstrapAuthorizationRedemption(
                    authorization_id=(
                        consumed.authorization_id
                    ),
                    customer_id=(
                        identity.customer_id
                    ),
                    consumed_at=(
                        consumed.consumed_at
                    ),
                    customer_identity=(
                        identity
                    ),
                )
            )

    def _issue_new(
        self,
        *,
        authorization_request_id: str,
        customer_id: str,
        code_challenge_s256: str,
        current_time: datetime,
    ) -> CustomerSetupBootstrapAuthorizationIssuance:
        issued_at = _serialize_timestamp(
            current_time
        )
        expires_at = _serialize_timestamp(
            current_time
            + _AUTHORIZATION_TTL
        )

        for _ in range(
            _GENERATION_ATTEMPTS
        ):
            authorization_id = (
                secrets.token_hex(
                    16
                )
            )

            if (
                self._authorization_store.get(
                    authorization_id=(
                        authorization_id
                    )
                )
                is not None
            ):
                continue

            authorization_code = (
                self._generate_authorization_code(
                    authorization_id
                )
            )

            verifier = (
                derive_customer_setup_bootstrap_authorization_verifier(
                    authorization_code
                )
            )

            if (
                self._authorization_store
                .get_by_verifier(
                    authorization_verifier_sha256=(
                        verifier
                    )
                )
                is not None
            ):
                continue

            record = (
                CustomerSetupBootstrapAuthorizationRecord(
                    authorization_request_id=(
                        authorization_request_id
                    ),
                    authorization_id=(
                        authorization_id
                    ),
                    customer_id=(
                        customer_id
                    ),
                    authorization_verifier_sha256=(
                        verifier
                    ),
                    code_challenge_s256=(
                        code_challenge_s256
                    ),
                    issued_at=(
                        issued_at
                    ),
                    expires_at=(
                        expires_at
                    ),
                    status=(
                        CustomerSetupBootstrapAuthorizationStatus
                        .ACTIVE
                    ),
                )
            )

            persisted = (
                self._authorization_store.insert(
                    record
                )
            )

            return self._build_issuance(
                persisted,
                authorization_code=(
                    authorization_code
                ),
            )

        raise RuntimeError(
            "Unable to generate unique bootstrap "
            "authorization."
        )

    def _rotate_existing_code(
        self,
        record: CustomerSetupBootstrapAuthorizationRecord,
    ) -> CustomerSetupBootstrapAuthorizationIssuance:
        for _ in range(
            _GENERATION_ATTEMPTS
        ):
            authorization_code = (
                self._generate_authorization_code(
                    record.authorization_id
                )
            )

            verifier = (
                derive_customer_setup_bootstrap_authorization_verifier(
                    authorization_code
                )
            )

            verifier_owner = (
                self._authorization_store
                .get_by_verifier(
                    authorization_verifier_sha256=(
                        verifier
                    )
                )
            )

            if (
                verifier_owner is not None
                and verifier_owner.authorization_id
                != record.authorization_id
            ):
                continue

            updated = (
                self._authorization_store
                .rotate_authorization_verifier(
                    authorization_id=(
                        record.authorization_id
                    ),
                    authorization_verifier_sha256=(
                        verifier
                    ),
                )
            )

            return self._build_issuance(
                updated,
                authorization_code=(
                    authorization_code
                ),
            )

        raise RuntimeError(
            "Unable to rotate bootstrap "
            "authorization code."
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not (
            self._customer_identity_registry
            .is_ready()
        ):
            raise RuntimeError(
                "Customer identity registry "
                "is not ready."
            )

        if not (
            self._authorization_store
            .is_ready()
        ):
            raise RuntimeError(
                "Bootstrap authorization store "
                "is not ready."
            )

    @staticmethod
    def _generate_authorization_code(
        authorization_id: str,
    ) -> str:
        secret = secrets.token_urlsafe(
            _AUTHORIZATION_SECRET_RANDOM_BYTES
        )

        return (
            f"{_AUTHORIZATION_PREFIX}."
            f"{authorization_id}."
            f"{secret}"
        )

    @staticmethod
    def _parse_authorization_code(
        authorization_code: str,
    ) -> tuple[
        str,
        str,
    ]:
        normalized = (
            _normalize_required_string(
                authorization_code,
                name="authorization_code",
            )
        )

        parts = normalized.split(
            "."
        )

        if len(
            parts
        ) != 3:
            raise ValueError(
                "Invalid bootstrap authorization."
            )

        prefix = parts[
            0
        ]
        authorization_id = parts[
            1
        ]
        secret = parts[
            2
        ]

        if (
            prefix
            != _AUTHORIZATION_PREFIX
            or not
            _AUTHORIZATION_ID_PATTERN.fullmatch(
                authorization_id
            )
            or not secret
        ):
            raise ValueError(
                "Invalid bootstrap authorization."
            )

        return (
            normalized,
            authorization_id,
        )

    @staticmethod
    def _is_expired(
        record: CustomerSetupBootstrapAuthorizationRecord,
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
    def _build_issuance(
        record: CustomerSetupBootstrapAuthorizationRecord,
        *,
        authorization_code: str,
    ) -> CustomerSetupBootstrapAuthorizationIssuance:
        return (
            CustomerSetupBootstrapAuthorizationIssuance(
                authorization_request_id=(
                    record.authorization_request_id
                ),
                authorization_id=(
                    record.authorization_id
                ),
                customer_id=(
                    record.customer_id
                ),
                issued_at=(
                    record.issued_at
                ),
                expires_at=(
                    record.expires_at
                ),
                authorization_code=(
                    authorization_code
                ),
            )
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

    if (
        not value
        or value.strip()
        != value
    ):
        raise ValueError(
            f"{name} is invalid."
        )

    return value


def _normalize_authorization_id(
    value,
) -> str:
    normalized = (
        _normalize_required_string(
            value,
            name="authorization_id",
        )
    )

    if not (
        _AUTHORIZATION_ID_PATTERN.fullmatch(
            normalized
        )
    ):
        raise ValueError(
            "authorization_id is invalid."
        )

    return normalized


def _normalize_authorization_verifier(
    value,
) -> str:
    normalized = (
        _normalize_required_string(
            value,
            name=(
                "authorization_verifier_sha256"
            ),
        )
    )

    if not (
        _AUTHORIZATION_VERIFIER_PATTERN.fullmatch(
            normalized
        )
    ):
        raise ValueError(
            "authorization_verifier_sha256 "
            "is invalid."
        )

    return normalized


def _normalize_code_challenge(
    value,
) -> str:
    normalized = (
        _normalize_required_string(
            value,
            name="code_challenge_s256",
        )
    )

    if not (
        _PKCE_S256_CHALLENGE_PATTERN.fullmatch(
            normalized
        )
    ):
        raise ValueError(
            "code_challenge_s256 is invalid."
        )

    return normalized


def _normalize_code_verifier(
    value,
) -> str:
    normalized = (
        _normalize_required_string(
            value,
            name="code_verifier",
        )
    )

    if not (
        _PKCE_CODE_VERIFIER_PATTERN.fullmatch(
            normalized
        )
    ):
        raise ValueError(
            "code_verifier is invalid."
        )

    return normalized


def _normalize_datetime(
    value,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "current_time must be datetime."
        )

    if (
        value.tzinfo
        is None
        or value.utcoffset()
        is None
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
    normalized = (
        _normalize_datetime(
            value
        )
    )

    return (
        normalized
        .isoformat(
            timespec="microseconds"
        )
        .replace(
            "+00:00",
            "Z",
        )
    )


def _parse_timestamp(
    value,
    *,
    name: str,
) -> datetime:
    normalized = (
        _normalize_required_string(
            value,
            name=name,
        )
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

    return _normalize_datetime(
        parsed
    )