from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import secrets
import threading
import uuid
from typing import Callable


_GRANT_PREFIX = "vps-connect-grant"
_GRANT_TTL = timedelta(minutes=10)
_SECRET_BYTES = 32
_ID_GENERATION_ATTEMPTS = 16


def _normalize_required_string(
    value: str,
    *,
    name: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{name} must be str."
        )

    if not value:
        raise ValueError(
            f"{name} must not be empty."
        )

    if value.strip() != value:
        raise ValueError(
            f"{name} must be normalized."
        )

    return value


def _normalize_aware_datetime(
    value: datetime,
    *,
    name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(
            f"{name} must be datetime."
        )

    if value.tzinfo is None:
        raise ValueError(
            f"{name} must be timezone-aware."
        )

    return value.astimezone(timezone.utc)


def _serialize_datetime(
    value: datetime,
) -> str:
    return (
        _normalize_aware_datetime(
            value,
            name="timestamp",
        )
        .isoformat()
    )


def _parse_datetime(
    value: str,
    *,
    name: str,
) -> datetime:
    normalized = _normalize_required_string(
        value,
        name=name,
    )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError as exc:
        raise ValueError(
            f"{name} must be valid datetime."
        ) from exc

    return _normalize_aware_datetime(
        parsed,
        name=name,
    )


class CustomerVPSConnectGrantStatus(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(
    frozen=True,
)
class CustomerVPSConnectGrantRecord:
    grant_id: str
    customer_id: str
    deployment_id: str
    agent_id: str
    account_fingerprint: str
    grant_sha256: str
    status: CustomerVPSConnectGrantStatus
    issued_at: str
    expires_at: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "grant_id",
            "customer_id",
            "deployment_id",
            "agent_id",
            "account_fingerprint",
            "grant_sha256",
            "issued_at",
            "expires_at",
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

        if not isinstance(
            self.status,
            CustomerVPSConnectGrantStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerVPSConnectGrantStatus."
            )

        issued_at = _parse_datetime(
            self.issued_at,
            name="issued_at",
        )
        expires_at = _parse_datetime(
            self.expires_at,
            name="expires_at",
        )

        if expires_at <= issued_at:
            raise ValueError(
                "expires_at must be later "
                "than issued_at."
            )


@dataclass(
    frozen=True,
)
class CustomerVPSConnectGrantIssuance:
    grant_id: str
    grant_credential: str
    customer_id: str
    deployment_id: str
    agent_id: str
    account_fingerprint: str
    issued_at: datetime
    expires_at: datetime


@dataclass(
    frozen=True,
)
class CustomerVPSConnectGrantAuthorization:
    customer_id: str
    deployment_id: str
    agent_id: str
    account_fingerprint: str
    expires_at: datetime


class CustomerVPSConnectGrantStore:
    def __init__(
        self,
        path: Path,
    ) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._ready = False
        self._records: dict[
            str,
            CustomerVPSConnectGrantRecord,
        ] = {}

    def initialize_empty(
        self,
    ) -> None:
        with self._lock:
            self._path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._records = {}
            self._write_records()
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if not self._path.is_file():
                raise RuntimeError(
                    "Customer VPS Connect grant "
                    "store does not exist."
                )

            raw = json.loads(
                self._path.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(raw, list):
                raise RuntimeError(
                    "Customer VPS Connect grant "
                    "store is invalid."
                )

            records = {}

            for item in raw:
                if not isinstance(item, dict):
                    raise RuntimeError(
                        "Customer VPS Connect grant "
                        "record is invalid."
                    )

                record = (
                    CustomerVPSConnectGrantRecord(
                        grant_id=item["grant_id"],
                        customer_id=item["customer_id"],
                        deployment_id=(
                            item["deployment_id"]
                        ),
                        agent_id=item["agent_id"],
                        account_fingerprint=(
                            item[
                                "account_fingerprint"
                            ]
                        ),
                        grant_sha256=(
                            item["grant_sha256"]
                        ),
                        status=(
                            CustomerVPSConnectGrantStatus(
                                item["status"]
                            )
                        ),
                        issued_at=item["issued_at"],
                        expires_at=item["expires_at"],
                    )
                )

                if record.grant_id in records:
                    raise RuntimeError(
                        "Duplicate Customer VPS "
                        "Connect grant identity."
                    )

                records[
                    record.grant_id
                ] = record

            self._records = records
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        with self._lock:
            return self._ready

    def register(
        self,
        record: CustomerVPSConnectGrantRecord,
    ) -> CustomerVPSConnectGrantRecord:
        with self._lock:
            self._require_ready()

            if record.grant_id in self._records:
                raise ValueError(
                    "Customer VPS Connect grant "
                    "already exists."
                )

            self._records[
                record.grant_id
            ] = record

            self._write_records()

            return record

    def get(
        self,
        *,
        grant_id: str,
    ) -> CustomerVPSConnectGrantRecord | None:
        normalized = _normalize_required_string(
            grant_id,
            name="grant_id",
        )

        with self._lock:
            self._require_ready()

            return self._records.get(
                normalized
            )

    def revoke(
        self,
        *,
        grant_id: str,
    ) -> CustomerVPSConnectGrantRecord:
        normalized = _normalize_required_string(
            grant_id,
            name="grant_id",
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                normalized
            )

            if existing is None:
                raise ValueError(
                    "Unknown Customer VPS "
                    "Connect grant."
                )

            if (
                existing.status
                is CustomerVPSConnectGrantStatus.REVOKED
            ):
                return existing

            updated = (
                CustomerVPSConnectGrantRecord(
                    grant_id=existing.grant_id,
                    customer_id=existing.customer_id,
                    deployment_id=(
                        existing.deployment_id
                    ),
                    agent_id=existing.agent_id,
                    account_fingerprint=(
                        existing.account_fingerprint
                    ),
                    grant_sha256=(
                        existing.grant_sha256
                    ),
                    status=(
                        CustomerVPSConnectGrantStatus
                        .REVOKED
                    ),
                    issued_at=existing.issued_at,
                    expires_at=existing.expires_at,
                )
            )

            self._records[
                normalized
            ] = updated

            self._write_records()

            return updated

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer VPS Connect grant "
                "store is not ready."
            )

    def _write_records(
        self,
    ) -> None:
        payload = []

        for record in self._records.values():
            payload.append(
                {
                    "grant_id": record.grant_id,
                    "customer_id": record.customer_id,
                    "deployment_id": (
                        record.deployment_id
                    ),
                    "agent_id": record.agent_id,
                    "account_fingerprint": (
                        record.account_fingerprint
                    ),
                    "grant_sha256": (
                        record.grant_sha256
                    ),
                    "status": record.status.value,
                    "issued_at": record.issued_at,
                    "expires_at": record.expires_at,
                }
            )

        encoded = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )

        temporary = self._path.with_name(
            self._path.name
            + "."
            + uuid.uuid4().hex
            + ".tmp"
        )

        try:
            temporary.write_text(
                encoded,
                encoding="utf-8",
            )
            temporary.replace(
                self._path
            )
        finally:
            if temporary.exists():
                temporary.unlink()


class CustomerVPSConnectGrantService:
    def __init__(
        self,
        *,
        grant_store: CustomerVPSConnectGrantStore,
        clock: Callable[[], datetime],
    ) -> None:
        if not isinstance(
            grant_store,
            CustomerVPSConnectGrantStore,
        ):
            raise TypeError(
                "grant_store must be "
                "CustomerVPSConnectGrantStore."
            )

        if not grant_store.is_ready():
            raise RuntimeError(
                "grant_store must be ready."
            )

        if not callable(clock):
            raise TypeError(
                "clock must be callable."
            )

        self._grant_store = grant_store
        self._clock = clock
        self._lock = threading.RLock()

    def issue(
        self,
        *,
        customer_id: str,
        deployment_id: str,
        agent_id: str,
        account_fingerprint: str,
    ) -> CustomerVPSConnectGrantIssuance:
        normalized_customer_id = (
            _normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )
        normalized_deployment_id = (
            _normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )
        normalized_agent_id = (
            _normalize_required_string(
                agent_id,
                name="agent_id",
            )
        )
        normalized_account_fingerprint = (
            _normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        with self._lock:
            issued_at = (
                _normalize_aware_datetime(
                    self._clock(),
                    name="clock",
                )
            )
            expires_at = (
                issued_at
                + _GRANT_TTL
            )

            for _ in range(
                _ID_GENERATION_ATTEMPTS
            ):
                grant_id = secrets.token_hex(
                    16
                )

                if (
                    self._grant_store.get(
                        grant_id=grant_id
                    )
                    is not None
                ):
                    continue

                secret = secrets.token_urlsafe(
                    _SECRET_BYTES
                )

                grant_credential = (
                    f"{_GRANT_PREFIX}."
                    f"{grant_id}."
                    f"{secret}"
                )

                record = (
                    CustomerVPSConnectGrantRecord(
                        grant_id=grant_id,
                        customer_id=(
                            normalized_customer_id
                        ),
                        deployment_id=(
                            normalized_deployment_id
                        ),
                        agent_id=(
                            normalized_agent_id
                        ),
                        account_fingerprint=(
                            normalized_account_fingerprint
                        ),
                        grant_sha256=(
                            self._derive_grant_sha256(
                                grant_credential
                            )
                        ),
                        status=(
                            CustomerVPSConnectGrantStatus
                            .ACTIVE
                        ),
                        issued_at=(
                            _serialize_datetime(
                                issued_at
                            )
                        ),
                        expires_at=(
                            _serialize_datetime(
                                expires_at
                            )
                        ),
                    )
                )

                self._grant_store.register(
                    record
                )

                return (
                    CustomerVPSConnectGrantIssuance(
                        grant_id=grant_id,
                        grant_credential=(
                            grant_credential
                        ),
                        customer_id=(
                            normalized_customer_id
                        ),
                        deployment_id=(
                            normalized_deployment_id
                        ),
                        agent_id=(
                            normalized_agent_id
                        ),
                        account_fingerprint=(
                            normalized_account_fingerprint
                        ),
                        issued_at=issued_at,
                        expires_at=expires_at,
                    )
                )

            raise RuntimeError(
                "Unable to generate unique "
                "Customer VPS Connect grant."
            )

    def authorize(
        self,
        *,
        grant_credential: str,
    ) -> CustomerVPSConnectGrantAuthorization:
        normalized = (
            _normalize_required_string(
                grant_credential,
                name="grant_credential",
            )
        )

        grant_id = self._parse_grant_id(
            normalized
        )

        record = self._grant_store.get(
            grant_id=grant_id
        )

        if (
            record is None
            or record.status
            is not CustomerVPSConnectGrantStatus.ACTIVE
        ):
            raise ValueError(
                "Customer VPS Connect grant is invalid."
            )

        supplied_sha256 = (
            self._derive_grant_sha256(
                normalized
            )
        )

        if not secrets.compare_digest(
            record.grant_sha256,
            supplied_sha256,
        ):
            raise ValueError(
                "Customer VPS Connect grant is invalid."
            )

        now = _normalize_aware_datetime(
            self._clock(),
            name="clock",
        )
        expires_at = _parse_datetime(
            record.expires_at,
            name="expires_at",
        )

        if now >= expires_at:
            raise ValueError(
                "Customer VPS Connect grant is invalid."
            )

        return (
            CustomerVPSConnectGrantAuthorization(
                customer_id=(
                    record.customer_id
                ),
                deployment_id=(
                    record.deployment_id
                ),
                agent_id=record.agent_id,
                account_fingerprint=(
                    record.account_fingerprint
                ),
                expires_at=expires_at,
            )
        )

    def revoke(
        self,
        *,
        grant_id: str,
    ) -> CustomerVPSConnectGrantRecord:
        return self._grant_store.revoke(
            grant_id=grant_id
        )

    @staticmethod
    def _derive_grant_sha256(
        grant_credential: str,
    ) -> str:
        return hashlib.sha256(
            grant_credential.encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _parse_grant_id(
        grant_credential: str,
    ) -> str:
        parts = grant_credential.split(
            ".",
            2,
        )

        if (
            len(parts) != 3
            or parts[0] != _GRANT_PREFIX
        ):
            raise ValueError(
                "Customer VPS Connect grant is invalid."
            )

        return _normalize_required_string(
            parts[1],
            name="grant_id",
        )
