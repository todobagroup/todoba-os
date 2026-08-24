"""
TODOBA Customer Deployment Entitlement Registry

Authoritative durable owner of commercial entitlement
state for individual customer deployments.

Entitlement identity:
    deployment_id

Lifecycle:
    no record   -> no entitlement
    ACTIVE      -> service entitlement is active
    SUSPENDED   -> service entitlement is suspended

SUSPENDED is intentionally reversible. A deployment may be
activated again after a controlled commercial renewal or
administrative decision.

Security and ownership rules:
- entitlement belongs to one deployment, not globally to a customer
- deployment identity must already exist in
  CustomerDeploymentRegistry
- customer_id and agent_id are never caller entitlement inputs
- unknown deployments fail closed before durable mutation
- persistence is durable before in-memory state is committed
- restore rejects corrupt, duplicate, or orphaned entitlement truth

This component does not:
- authenticate customers
- authorize customer ownership of a deployment
- process payments or billing providers
- store payment identifiers
- parse HTTP requests
- access deployment secrets
- build or deliver deployment packages
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import uuid

from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)


STORE_VERSION = 1


class CustomerDeploymentEntitlementStatus(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True)
class CustomerDeploymentEntitlement:
    """
    Immutable durable entitlement truth for one deployment.
    """

    deployment_id: str
    status: CustomerDeploymentEntitlementStatus

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "deployment_id",
            self._normalize_required_string(
                self.deployment_id,
                name="deployment_id",
            ),
        )

        if not isinstance(
            self.status,
            CustomerDeploymentEntitlementStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerDeploymentEntitlementStatus."
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
                f"{name} must not be empty."
            )

        return normalized


class CustomerDeploymentEntitlementRegistry:
    """
    Durable deployment-level commercial entitlement owner.
    """

    def __init__(
        self,
        storage_path: Path,
        *,
        deployment_registry: CustomerDeploymentRegistry,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        if not isinstance(
            deployment_registry,
            CustomerDeploymentRegistry,
        ):
            raise TypeError(
                "deployment_registry must be "
                "CustomerDeploymentRegistry."
            )

        if not deployment_registry.is_ready():
            raise ValueError(
                "deployment_registry must be ready."
            )

        self.storage_path = storage_path
        self._deployment_registry = (
            deployment_registry
        )

        self._entitlements: dict[
            str,
            CustomerDeploymentEntitlement,
        ] = {}

        self._ready = False

        if self.storage_path.exists():
            self._restore_from_disk()

    def initialize_empty(
        self,
    ) -> None:
        if self._ready:
            raise ValueError(
                "Customer deployment entitlement registry "
                "is already ready."
            )

        candidate: dict[
            str,
            CustomerDeploymentEntitlement,
        ] = {}

        self._write_entitlements(
            candidate
        )

        self._entitlements = candidate
        self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def activate(
        self,
        *,
        deployment_id: str,
    ) -> CustomerDeploymentEntitlement:
        """
        Activate entitlement for one authoritative deployment.

        If already ACTIVE, the operation is idempotent.
        A SUSPENDED entitlement may be activated again.
        """

        self._require_ready()

        normalized_deployment_id = (
            self._require_existing_deployment(
                deployment_id
            )
        )

        existing = self._entitlements.get(
            normalized_deployment_id
        )

        if (
            existing is not None
            and existing.status
            is CustomerDeploymentEntitlementStatus.ACTIVE
        ):
            return existing

        entitlement = CustomerDeploymentEntitlement(
            deployment_id=normalized_deployment_id,
            status=(
                CustomerDeploymentEntitlementStatus.ACTIVE
            ),
        )

        candidate = dict(
            self._entitlements
        )

        candidate[
            normalized_deployment_id
        ] = entitlement

        self._write_entitlements(
            candidate
        )

        self._entitlements = candidate

        return entitlement

    def suspend(
        self,
        *,
        deployment_id: str,
    ) -> CustomerDeploymentEntitlement:
        """
        Suspend an existing entitlement.

        Suspension is reversible through activate().
        A deployment with no entitlement cannot be suspended,
        because absence already means no entitlement.
        """

        self._require_ready()

        normalized_deployment_id = (
            self._require_existing_deployment(
                deployment_id
            )
        )

        existing = self._entitlements.get(
            normalized_deployment_id
        )

        if existing is None:
            raise ValueError(
                "Customer deployment entitlement "
                "does not exist."
            )

        if (
            existing.status
            is CustomerDeploymentEntitlementStatus.SUSPENDED
        ):
            return existing

        entitlement = CustomerDeploymentEntitlement(
            deployment_id=normalized_deployment_id,
            status=(
                CustomerDeploymentEntitlementStatus.SUSPENDED
            ),
        )

        candidate = dict(
            self._entitlements
        )

        candidate[
            normalized_deployment_id
        ] = entitlement

        self._write_entitlements(
            candidate
        )

        self._entitlements = candidate

        return entitlement

    def get(
        self,
        *,
        deployment_id: str,
    ) -> CustomerDeploymentEntitlement | None:
        self._require_ready()

        normalized_deployment_id = (
            self._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        return self._entitlements.get(
            normalized_deployment_id
        )

    def is_active(
        self,
        *,
        deployment_id: str,
    ) -> bool:
        self._require_ready()

        try:
            entitlement = self.get(
                deployment_id=deployment_id
            )
        except (
            TypeError,
            ValueError,
        ):
            return False

        return (
            entitlement is not None
            and entitlement.status
            is CustomerDeploymentEntitlementStatus.ACTIVE
        )

    def all(
        self,
    ) -> tuple[
        CustomerDeploymentEntitlement,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._entitlements[
                deployment_id
            ]
            for deployment_id in sorted(
                self._entitlements
            )
        )

    def size(
        self,
    ) -> int:
        self._require_ready()

        return len(
            self._entitlements
        )

    def _require_existing_deployment(
        self,
        deployment_id: str,
    ) -> str:
        normalized_deployment_id = (
            self._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        deployment = (
            self._deployment_registry.get(
                deployment_id=(
                    normalized_deployment_id
                )
            )
        )

        if deployment is None:
            raise ValueError(
                "Customer deployment does not exist."
            )

        return deployment.deployment_id

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer deployment entitlement registry "
                "is not initialized."
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
                "Customer deployment entitlement store "
                "is unreadable."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer deployment entitlement store "
                "must contain an object."
            )

        if set(
            payload
        ) != {
            "version",
            "entitlements",
        }:
            raise ValueError(
                "Customer deployment entitlement store "
                "has invalid fields."
            )

        if payload[
            "version"
        ] != STORE_VERSION:
            raise ValueError(
                "Unsupported customer deployment "
                "entitlement store version."
            )

        items = payload[
            "entitlements"
        ]

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer deployment entitlement items "
                "must be a list."
            )

        restored: dict[
            str,
            CustomerDeploymentEntitlement,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer deployment entitlement item "
                    "must be an object."
                )

            if set(
                item
            ) != {
                "deployment_id",
                "status",
            }:
                raise ValueError(
                    "Customer deployment entitlement item "
                    "has invalid fields."
                )

            try:
                status = (
                    CustomerDeploymentEntitlementStatus(
                        item[
                            "status"
                        ]
                    )
                )

                entitlement = (
                    CustomerDeploymentEntitlement(
                        deployment_id=item[
                            "deployment_id"
                        ],
                        status=status,
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Customer deployment entitlement item "
                    "is invalid."
                ) from exc

            if (
                entitlement.deployment_id
                in restored
            ):
                raise ValueError(
                    "Duplicate customer deployment "
                    "entitlement."
                )

            try:
                deployment = (
                    self._deployment_registry.get(
                        deployment_id=(
                            entitlement.deployment_id
                        )
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Customer deployment entitlement "
                    "references invalid deployment."
                ) from exc

            if deployment is None:
                raise ValueError(
                    "Customer deployment entitlement "
                    "references unknown deployment."
                )

            restored[
                entitlement.deployment_id
            ] = entitlement

        self._entitlements = restored
        self._ready = True

    def _write_entitlements(
        self,
        entitlements: dict[
            str,
            CustomerDeploymentEntitlement,
        ],
    ) -> None:
        items = []

        for deployment_id in sorted(
            entitlements
        ):
            entitlement = entitlements[
                deployment_id
            ]

            items.append(
                {
                    "deployment_id": (
                        entitlement.deployment_id
                    ),
                    "status": (
                        entitlement.status.value
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "entitlements": items,
        }

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.storage_path.with_name(
                self.storage_path.name
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
            ) as destination:
                json.dump(
                    payload,
                    destination,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )

                destination.write(
                    "\n"
                )

                destination.flush()
                os.fsync(
                    destination.fileno()
                )

            os.replace(
                temporary_path,
                self.storage_path,
            )
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

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

        return normalized
