"""
TODOBA Customer Access Credential Registry

Owns durable commercial customer access credential state.

Trust model:
- customer_id is owned by CustomerIdentityRegistry
- access credentials are high-entropy opaque bearer secrets
- plaintext access credentials are never persisted
- durable state stores only a SHA-256 verifier
- credential_id is a public lookup identifier, not a secret
- revoked credentials remain durable and cannot become active again

This component owns:
- access credential issuance
- durable verifier storage
- credential revocation
- restart restoration
- collision rejection/retry

This component does not:
- authenticate HTTP requests
- parse Authorization headers
- create customer sessions
- own customer identity
- own deployments
- own subscriptions or entitlement
- deliver customer packages
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import threading

from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)


STORE_VERSION = 1

CUSTOMER_ACCESS_CREDENTIAL_PREFIX = "tdbca1"

_CREDENTIAL_ID_PATTERN = re.compile(
    r"^[0-9a-f]{32}$"
)

_VERIFIER_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)

_MAX_GENERATION_ATTEMPTS = 32


class CustomerAccessCredentialStatus(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(
    frozen=True,
)
class CustomerAccessCredentialRecord:
    """
    Durable non-secret customer access credential record.
    """

    credential_id: str
    customer_id: str
    verifier_sha256: str
    status: CustomerAccessCredentialStatus

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "credential_id",
            self._normalize_credential_id(
                self.credential_id
            ),
        )

        object.__setattr__(
            self,
            "customer_id",
            self._normalize_required_string(
                self.customer_id,
                name="customer_id",
            ),
        )

        object.__setattr__(
            self,
            "verifier_sha256",
            self._normalize_verifier(
                self.verifier_sha256
            ),
        )

        if not isinstance(
            self.status,
            CustomerAccessCredentialStatus,
        ):
            try:
                normalized_status = (
                    CustomerAccessCredentialStatus(
                        self.status
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Invalid customer access "
                    "credential status."
                ) from error

            object.__setattr__(
                self,
                "status",
                normalized_status,
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
    def _normalize_credential_id(
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "credential_id must be str."
            )

        normalized = value.strip()

        if not _CREDENTIAL_ID_PATTERN.fullmatch(
            normalized
        ):
            raise ValueError(
                "Invalid customer access credential_id."
            )

        return normalized

    @staticmethod
    def _normalize_verifier(
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "verifier_sha256 must be str."
            )

        normalized = value.strip()

        if not _VERIFIER_PATTERN.fullmatch(
            normalized
        ):
            raise ValueError(
                "Invalid customer access "
                "credential verifier."
            )

        return normalized

    @property
    def is_active(
        self,
    ) -> bool:
        return (
            self.status
            is CustomerAccessCredentialStatus.ACTIVE
        )


@dataclass(
    frozen=True,
)
class IssuedCustomerAccessCredential:
    """
    One-time issuance result.

    access_credential is intentionally excluded from repr
    so normal logging/debug representation does not expose
    the bearer secret.
    """

    credential_id: str
    customer_id: str

    access_credential: str = field(
        repr=False,
    )

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "credential_id",
            CustomerAccessCredentialRecord
            ._normalize_credential_id(
                self.credential_id
            ),
        )

        object.__setattr__(
            self,
            "customer_id",
            CustomerAccessCredentialRecord
            ._normalize_required_string(
                self.customer_id,
                name="customer_id",
            ),
        )

        object.__setattr__(
            self,
            "access_credential",
            self._normalize_access_credential(
                self.access_credential
            ),
        )

    @staticmethod
    def _normalize_access_credential(
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "access_credential must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "access_credential is required."
            )

        return normalized


def derive_customer_access_credential_verifier(
    access_credential: str,
) -> str:
    """
    Derive the durable verifier for a high-entropy
    customer access credential.

    SHA-256 is used here for a machine-generated
    256-bit-class random bearer secret, not a
    human-selected password.
    """

    normalized = (
        IssuedCustomerAccessCredential
        ._normalize_access_credential(
            access_credential
        )
    )

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


class CustomerAccessCredentialRegistry:
    """
    Durable owner of customer access credential records.

    A customer identity must already exist before a
    credential can be issued.

    Durable state advances before the plaintext credential
    is returned to the caller.
    """

    def __init__(
        self,
        storage_path: Path,
        *,
        customer_identity_registry: (
            CustomerIdentityRegistry
        ),
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

        self.customer_identity_registry = (
            customer_identity_registry
        )

        self._records: dict[
            str,
            CustomerAccessCredentialRecord,
        ] = {}

        self._credential_id_by_verifier: dict[
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
            self._credential_id_by_verifier = {}
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def issue(
        self,
        *,
        customer_id: str,
    ) -> IssuedCustomerAccessCredential:
        """
        Issue one new customer access credential.

        The customer must already exist in the
        authoritative CustomerIdentityRegistry.

        The plaintext credential is returned only after
        durable verifier persistence succeeds.
        """

        normalized_customer_id = (
            self._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        with self._lock:
            self._require_ready()

            if not self.customer_identity_registry.contains(
                customer_id=normalized_customer_id
            ):
                raise ValueError(
                    "Unknown customer identity."
                )

            for _ in range(
                _MAX_GENERATION_ATTEMPTS
            ):
                credential_id = (
                    secrets.token_hex(
                        16
                    )
                )

                secret = secrets.token_urlsafe(
                    32
                )

                access_credential = (
                    f"{CUSTOMER_ACCESS_CREDENTIAL_PREFIX}"
                    f".{credential_id}"
                    f".{secret}"
                )

                verifier = (
                    derive_customer_access_credential_verifier(
                        access_credential
                    )
                )

                if (
                    credential_id
                    in self._records
                ):
                    continue

                if (
                    verifier
                    in self._credential_id_by_verifier
                ):
                    continue

                record = (
                    CustomerAccessCredentialRecord(
                        credential_id=credential_id,
                        customer_id=(
                            normalized_customer_id
                        ),
                        verifier_sha256=verifier,
                        status=(
                            CustomerAccessCredentialStatus
                            .ACTIVE
                        ),
                    )
                )

                candidate = dict(
                    self._records
                )

                candidate[
                    credential_id
                ] = record

                self._write_records(
                    candidate
                )

                self._records = candidate

                verifier_index = dict(
                    self._credential_id_by_verifier
                )

                verifier_index[
                    verifier
                ] = credential_id

                self._credential_id_by_verifier = (
                    verifier_index
                )

                return IssuedCustomerAccessCredential(
                    credential_id=credential_id,
                    customer_id=(
                        normalized_customer_id
                    ),
                    access_credential=(
                        access_credential
                    ),
                )

            raise RuntimeError(
                "Unable to generate unique customer "
                "access credential."
            )

    def revoke(
        self,
        *,
        credential_id: str,
    ) -> CustomerAccessCredentialRecord:
        """
        Permanently revoke one credential.

        Revocation is idempotent.
        Unknown credential IDs fail closed.
        """

        normalized_credential_id = (
            CustomerAccessCredentialRecord
            ._normalize_credential_id(
                credential_id
            )
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                normalized_credential_id
            )

            if existing is None:
                raise ValueError(
                    "Unknown customer access "
                    "credential."
                )

            if (
                existing.status
                is CustomerAccessCredentialStatus
                .REVOKED
            ):
                return existing

            revoked = (
                CustomerAccessCredentialRecord(
                    credential_id=(
                        existing.credential_id
                    ),
                    customer_id=(
                        existing.customer_id
                    ),
                    verifier_sha256=(
                        existing.verifier_sha256
                    ),
                    status=(
                        CustomerAccessCredentialStatus
                        .REVOKED
                    ),
                )
            )

            candidate = dict(
                self._records
            )

            candidate[
                normalized_credential_id
            ] = revoked

            self._write_records(
                candidate
            )

            self._records = candidate

            return revoked

    def get(
        self,
        *,
        credential_id: str,
    ) -> CustomerAccessCredentialRecord | None:
        self._require_ready()

        normalized_credential_id = (
            CustomerAccessCredentialRecord
            ._normalize_credential_id(
                credential_id
            )
        )

        return self._records.get(
            normalized_credential_id
        )

    def all_for_customer(
        self,
        *,
        customer_id: str,
    ) -> tuple[
        CustomerAccessCredentialRecord,
        ...,
    ]:
        self._require_ready()

        normalized_customer_id = (
            self._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        return tuple(
            self._records[
                credential_id
            ]
            for credential_id in sorted(
                self._records
            )
            if (
                self._records[
                    credential_id
                ].customer_id
                == normalized_customer_id
            )
        )

    def all(
        self,
    ) -> tuple[
        CustomerAccessCredentialRecord,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._records[
                credential_id
            ]
            for credential_id in sorted(
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
                "Customer access credential registry "
                "is not initialized."
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
                "Customer access credential payload "
                "must be an object."
            )

        if set(
            payload
        ) != {
            "version",
            "credentials",
        }:
            raise ValueError(
                "Customer access credential payload "
                "has invalid fields."
            )

        if payload.get(
            "version"
        ) != STORE_VERSION:
            raise ValueError(
                "Unsupported customer access "
                "credential registry version."
            )

        items = payload.get(
            "credentials"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer access credential records "
                "must be a list."
            )

        restored: dict[
            str,
            CustomerAccessCredentialRecord,
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
                    "Customer access credential item "
                    "must be an object."
                )

            if set(
                item
            ) != {
                "credential_id",
                "customer_id",
                "verifier_sha256",
                "status",
            }:
                raise ValueError(
                    "Customer access credential item "
                    "has invalid fields."
                )

            record = (
                CustomerAccessCredentialRecord(
                    credential_id=item[
                        "credential_id"
                    ],
                    customer_id=item[
                        "customer_id"
                    ],
                    verifier_sha256=item[
                        "verifier_sha256"
                    ],
                    status=item[
                        "status"
                    ],
                )
            )

            if not (
                self.customer_identity_registry
                .contains(
                    customer_id=(
                        record.customer_id
                    )
                )
            ):
                raise ValueError(
                    "Customer access credential "
                    "references unknown customer."
                )

            if (
                record.credential_id
                in restored
            ):
                raise ValueError(
                    "Duplicate customer access "
                    "credential_id."
                )

            if (
                record.verifier_sha256
                in verifier_index
            ):
                raise ValueError(
                    "Duplicate customer access "
                    "credential verifier."
                )

            restored[
                record.credential_id
            ] = record

            verifier_index[
                record.verifier_sha256
            ] = record.credential_id

        self._records = restored
        self._credential_id_by_verifier = (
            verifier_index
        )
        self._ready = True

    def _write_records(
        self,
        records: dict[
            str,
            CustomerAccessCredentialRecord,
        ],
    ) -> None:
        items = []

        for credential_id in sorted(
            records
        ):
            record = records[
                credential_id
            ]

            items.append(
                {
                    "credential_id": (
                        record.credential_id
                    ),
                    "customer_id": (
                        record.customer_id
                    ),
                    "verifier_sha256": (
                        record.verifier_sha256
                    ),
                    "status": (
                        record.status.value
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "credentials": items,
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
            temporary_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            os.replace(
                temporary_path,
                self.storage_path,
            )
        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()

            raise
