"""
TODOBA Customer Access Provisioning Service

Safely provisions commercial customer access for one
already-existing customer deployment.

Trust boundary:

    provisioning_request_id
    customer_id
    deployment_id
        -> authoritative deployment lookup
        -> verify deployment ownership before mutation
        -> durable provisioning request binding
        -> customer identity registration
        -> request-correlated credential issuance
        -> deployment entitlement activation
        -> one-time plaintext customer access credential

Crash-safety rules:
- request identity is durably bound before downstream
  commercial access mutation
- customer identity registration is idempotent
- correlated credential issuance is retry-safe
- entitlement activation is idempotent
- retries may rotate credential plaintext while preserving
  the same credential_id
- plaintext bearer credentials are never persisted here
- credential_id is not duplicated into provisioning state

This component does not:
- authenticate HTTP requests
- parse Authorization headers
- deliver deployment packages
- process payments or subscriptions
- access deployment secret material
- build or compile Trusted Agent artifacts
"""

from dataclasses import dataclass
from pathlib import Path
import json
import os
import threading

from backend.commercial.customer_access_credential_registry import (
    CustomerAccessCredentialRegistry,
    IssuedCustomerAccessCredential,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)


STORE_VERSION = 1


@dataclass(
    frozen=True,
)
class CustomerAccessProvisioningRecord:
    """
    Durable non-secret binding for one provisioning request.

    Identity:
        provisioning_request_id

    The record deliberately does not contain credential_id
    or plaintext credential material. Credential correlation
    remains authoritative in CustomerAccessCredentialRegistry.
    """

    provisioning_request_id: str
    customer_id: str
    deployment_id: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "provisioning_request_id",
            "customer_id",
            "deployment_id",
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


class CustomerAccessProvisioningStore:
    """
    Durable idempotency owner for customer access
    provisioning requests.

    One provisioning_request_id may bind to exactly one
    customer_id + deployment_id pair.
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
            CustomerAccessProvisioningRecord,
        ] = {}

        self._ready = False
        self._lock = threading.RLock()

        if self.storage_path.exists():
            self._restore_from_disk()

    def initialize_empty(
        self,
    ) -> None:
        """
        Explicitly initialize a new empty provisioning store.

        Missing durable storage is never silently treated as
        initialized commercial state.
        """

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
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        record: CustomerAccessProvisioningRecord,
    ) -> CustomerAccessProvisioningRecord:
        """
        Persist one request binding.

        Identical retry is idempotent.
        Conflicting reuse of a request identity fails closed.
        """

        if not isinstance(
            record,
            CustomerAccessProvisioningRecord,
        ):
            raise TypeError(
                "CustomerAccessProvisioningStore requires "
                "CustomerAccessProvisioningRecord."
            )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                record.provisioning_request_id
            )

            if existing is not None:
                if existing != record:
                    raise ValueError(
                        "Customer access provisioning "
                        "request is already bound to "
                        "different commercial identity."
                    )

                return existing

            candidate = dict(
                self._records
            )

            candidate[
                record.provisioning_request_id
            ] = record

            self._write_records(
                candidate
            )

            self._records = candidate

            return record

    def get(
        self,
        *,
        provisioning_request_id: str,
    ) -> CustomerAccessProvisioningRecord | None:
        self._require_ready()

        normalized_request_id = (
            CustomerAccessProvisioningRecord
            ._normalize_required_string(
                provisioning_request_id,
                name="provisioning_request_id",
            )
        )

        return self._records.get(
            normalized_request_id
        )

    def all(
        self,
    ) -> tuple[
        CustomerAccessProvisioningRecord,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._records[
                request_id
            ]
            for request_id in sorted(
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
                "Customer access provisioning store "
                "is not initialized."
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
                "Customer access provisioning payload "
                "must be an object."
            )

        if set(
            payload
        ) != {
            "version",
            "records",
        }:
            raise ValueError(
                "Customer access provisioning payload "
                "has invalid fields."
            )

        if payload.get(
            "version"
        ) != STORE_VERSION:
            raise ValueError(
                "Unsupported customer access provisioning "
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
                "Customer access provisioning records "
                "must be a list."
            )

        restored: dict[
            str,
            CustomerAccessProvisioningRecord,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer access provisioning item "
                    "must be an object."
                )

            if set(
                item
            ) != {
                "provisioning_request_id",
                "customer_id",
                "deployment_id",
            }:
                raise ValueError(
                    "Customer access provisioning item "
                    "has invalid fields."
                )

            record = (
                CustomerAccessProvisioningRecord(
                    provisioning_request_id=item[
                        "provisioning_request_id"
                    ],
                    customer_id=item[
                        "customer_id"
                    ],
                    deployment_id=item[
                        "deployment_id"
                    ],
                )
            )

            if (
                record.provisioning_request_id
                in restored
            ):
                raise ValueError(
                    "Duplicate customer access "
                    "provisioning request."
                )

            restored[
                record.provisioning_request_id
            ] = record

        self._records = restored
        self._ready = True

    def _write_records(
        self,
        records: dict[
            str,
            CustomerAccessProvisioningRecord,
        ],
    ) -> None:
        items = []

        for request_id in sorted(
            records
        ):
            record = records[
                request_id
            ]

            items.append(
                {
                    "provisioning_request_id": (
                        record.provisioning_request_id
                    ),
                    "customer_id": (
                        record.customer_id
                    ),
                    "deployment_id": (
                        record.deployment_id
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


@dataclass(
    frozen=True,
    repr=False,
)
class CustomerAccessProvisioningResult:
    """
    One successful customer access provisioning result.

    The bearer credential is intentionally excluded from
    repr so routine logging cannot expose plaintext access
    material.
    """

    provisioning_request_id: str
    customer_id: str
    deployment_id: str
    credential_id: str
    access_credential: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "provisioning_request_id",
            "customer_id",
            "deployment_id",
            "credential_id",
            "access_credential",
        ):
            object.__setattr__(
                self,
                name,
                CustomerAccessProvisioningRecord
                ._normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerAccessProvisioningResult("
            f"provisioning_request_id="
            f"{self.provisioning_request_id!r}, "
            f"customer_id={self.customer_id!r}, "
            f"deployment_id={self.deployment_id!r}, "
            f"credential_id={self.credential_id!r}, "
            "access_credential=<redacted>)"
        )


class CustomerAccessProvisioningService:
    """
    Coordinate one retry-safe commercial customer access
    provisioning operation.
    """

    def __init__(
        self,
        *,
        provisioning_store: (
            CustomerAccessProvisioningStore
        ),
        customer_identity_registry: (
            CustomerIdentityRegistry
        ),
        credential_registry: (
            CustomerAccessCredentialRegistry
        ),
        deployment_registry: (
            CustomerDeploymentRegistry
        ),
        entitlement_registry: (
            CustomerDeploymentEntitlementRegistry
        ),
    ) -> None:
        if not isinstance(
            provisioning_store,
            CustomerAccessProvisioningStore,
        ):
            raise TypeError(
                "provisioning_store must be "
                "CustomerAccessProvisioningStore."
            )

        if not isinstance(
            customer_identity_registry,
            CustomerIdentityRegistry,
        ):
            raise TypeError(
                "customer_identity_registry must be "
                "CustomerIdentityRegistry."
            )

        if not isinstance(
            credential_registry,
            CustomerAccessCredentialRegistry,
        ):
            raise TypeError(
                "credential_registry must be "
                "CustomerAccessCredentialRegistry."
            )

        if not isinstance(
            deployment_registry,
            CustomerDeploymentRegistry,
        ):
            raise TypeError(
                "deployment_registry must be "
                "CustomerDeploymentRegistry."
            )

        if not isinstance(
            entitlement_registry,
            CustomerDeploymentEntitlementRegistry,
        ):
            raise TypeError(
                "entitlement_registry must be "
                "CustomerDeploymentEntitlementRegistry."
            )

        if not provisioning_store.is_ready():
            raise RuntimeError(
                "Customer access provisioning store "
                "is not initialized."
            )

        if not customer_identity_registry.is_ready():
            raise RuntimeError(
                "Customer identity registry is not "
                "initialized."
            )

        if not credential_registry.is_ready():
            raise RuntimeError(
                "Customer access credential registry "
                "is not initialized."
            )

        if not deployment_registry.is_ready():
            raise RuntimeError(
                "Customer deployment registry is not "
                "initialized."
            )

        if not entitlement_registry.is_ready():
            raise RuntimeError(
                "Customer deployment entitlement registry "
                "is not initialized."
            )

        self._provisioning_store = (
            provisioning_store
        )

        self._customer_identity_registry = (
            customer_identity_registry
        )

        self._credential_registry = (
            credential_registry
        )

        self._deployment_registry = (
            deployment_registry
        )

        self._entitlement_registry = (
            entitlement_registry
        )

        self._lock = threading.RLock()

    def provision(
        self,
        *,
        provisioning_request_id: str,
        customer_id: str,
        deployment_id: str,
    ) -> CustomerAccessProvisioningResult:
        """
        Provision customer access for one authoritative
        deployment.

        Ownership is verified before any durable mutation.

        Retry with the same request/customer/deployment:
        - converges on the same request binding
        - reuses the same credential_id
        - rotates credential plaintext safely
        - leaves entitlement ACTIVE
        """

        normalized_request_id = (
            CustomerAccessProvisioningRecord
            ._normalize_required_string(
                provisioning_request_id,
                name="provisioning_request_id",
            )
        )

        normalized_customer_id = (
            CustomerAccessProvisioningRecord
            ._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        normalized_deployment_id = (
            CustomerAccessProvisioningRecord
            ._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        with self._lock:
            self._require_sources_ready()

            deployment = (
                self._deployment_registry.get(
                    deployment_id=(
                        normalized_deployment_id
                    )
                )
            )

            if deployment is None:
                raise ValueError(
                    "Unknown customer deployment."
                )

            if (
                deployment.customer_id
                != normalized_customer_id
            ):
                raise ValueError(
                    "Customer does not own deployment."
                )

            requested_record = (
                CustomerAccessProvisioningRecord(
                    provisioning_request_id=(
                        normalized_request_id
                    ),
                    customer_id=(
                        normalized_customer_id
                    ),
                    deployment_id=(
                        normalized_deployment_id
                    ),
                )
            )

            existing_record = (
                self._provisioning_store.get(
                    provisioning_request_id=(
                        normalized_request_id
                    )
                )
            )

            if (
                existing_record is not None
                and existing_record
                != requested_record
            ):
                raise ValueError(
                    "Customer access provisioning request "
                    "is already bound to different "
                    "commercial identity."
                )

            self._provisioning_store.register(
                requested_record
            )

            identity = (
                self._customer_identity_registry.register(
                    CustomerIdentity(
                        customer_id=(
                            normalized_customer_id
                        )
                    )
                )
            )

            issued = (
                self._credential_registry
                .issue_for_request(
                    customer_id=(
                        identity.customer_id
                    ),
                    issuance_request_id=(
                        normalized_request_id
                    ),
                )
            )

            self._entitlement_registry.activate(
                deployment_id=(
                    deployment.deployment_id
                )
            )

            return self._build_result(
                record=requested_record,
                issued=issued,
            )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._provisioning_store.is_ready():
            raise RuntimeError(
                "Customer access provisioning store "
                "is not initialized."
            )

        if not self._customer_identity_registry.is_ready():
            raise RuntimeError(
                "Customer identity registry is not "
                "initialized."
            )

        if not self._credential_registry.is_ready():
            raise RuntimeError(
                "Customer access credential registry "
                "is not initialized."
            )

        if not self._deployment_registry.is_ready():
            raise RuntimeError(
                "Customer deployment registry is not "
                "initialized."
            )

        if not self._entitlement_registry.is_ready():
            raise RuntimeError(
                "Customer deployment entitlement registry "
                "is not initialized."
            )

    @staticmethod
    def _build_result(
        *,
        record: CustomerAccessProvisioningRecord,
        issued: IssuedCustomerAccessCredential,
    ) -> CustomerAccessProvisioningResult:
        if (
            issued.customer_id
            != record.customer_id
        ):
            raise RuntimeError(
                "Issued credential customer identity "
                "does not match provisioning request."
            )

        return CustomerAccessProvisioningResult(
            provisioning_request_id=(
                record.provisioning_request_id
            ),
            customer_id=record.customer_id,
            deployment_id=record.deployment_id,
            credential_id=issued.credential_id,
            access_credential=(
                issued.access_credential
            ),
        )
