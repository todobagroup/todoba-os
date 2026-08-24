"""
TODOBA Customer Identity Registry

Owns durable commercial customer identity.

Identity:
    customer_id

One customer identity may own zero, one, or many customer
deployments. Deployment ownership remains the responsibility
of CustomerDeploymentRegistry.

The registry supports:
- durable customer identity
- idempotent registration
- atomic bulk registration for legacy adoption
- deterministic restore
- fail-closed duplicate/corrupt persistence handling

This component does not:
- authenticate customers
- store passwords, tokens, email, or phone numbers
- own subscriptions or entitlement
- own customer deployments
- own Trusted Agent identity
- own package delivery
"""

from collections.abc import Iterable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading


STORE_VERSION = 1


@dataclass(
    frozen=True,
)
class CustomerIdentity:
    """
    Immutable TODOBA commercial customer identity.
    """

    customer_id: str

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "customer_id",
            self._normalize_required_string(
                self.customer_id,
                name="customer_id",
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


class CustomerIdentityRegistry:
    """
    Durable authoritative owner of commercial customer IDs.

    Registration rules:
    - first customer identity is accepted
    - identical retry is idempotent
    - bulk registration validates the complete candidate
      before durable state changes
    - duplicate customer IDs in one bulk request converge
      on one identity
    - durable state is written before RAM advances
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

        self._customers: dict[
            str,
            CustomerIdentity,
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

            self._write_customers(
                {}
            )

            self._customers = {}
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        identity: CustomerIdentity,
    ) -> CustomerIdentity:
        """
        Register one customer identity.

        Identical retry is idempotent.
        """

        if not isinstance(
            identity,
            CustomerIdentity,
        ):
            raise TypeError(
                "CustomerIdentityRegistry requires "
                "CustomerIdentity."
            )

        with self._lock:
            self._require_ready()

            existing = self._customers.get(
                identity.customer_id
            )

            if existing is not None:
                return existing

            candidate = dict(
                self._customers
            )

            candidate[
                identity.customer_id
            ] = identity

            self._write_customers(
                candidate
            )

            self._customers = candidate

            return identity

    def register_many(
        self,
        identities: Iterable[
            CustomerIdentity
        ],
    ) -> tuple[
        CustomerIdentity,
        ...,
    ]:
        """
        Atomically register a collection of customer IDs.

        The complete request is validated before durable
        state changes. Duplicate identical customer IDs
        within the request converge on one identity.

        This method is intended to support safe adoption of
        customer IDs that already exist in durable
        commercial deployment truth.
        """

        if isinstance(
            identities,
            (
                str,
                bytes,
            ),
        ):
            raise TypeError(
                "identities must be an iterable of "
                "CustomerIdentity."
            )

        try:
            supplied = tuple(
                identities
            )
        except TypeError as error:
            raise TypeError(
                "identities must be iterable."
            ) from error

        prepared: dict[
            str,
            CustomerIdentity,
        ] = {}

        for identity in supplied:
            if not isinstance(
                identity,
                CustomerIdentity,
            ):
                raise TypeError(
                    "register_many requires only "
                    "CustomerIdentity values."
                )

            prepared[
                identity.customer_id
            ] = identity

        with self._lock:
            self._require_ready()

            candidate = dict(
                self._customers
            )

            for (
                customer_id,
                identity,
            ) in prepared.items():
                existing = candidate.get(
                    customer_id
                )

                if existing is not None:
                    continue

                candidate[
                    customer_id
                ] = identity

            if candidate != self._customers:
                self._write_customers(
                    candidate
                )

                self._customers = candidate

            return tuple(
                self._customers[
                    customer_id
                ]
                for customer_id in sorted(
                    prepared
                )
            )

    def get(
        self,
        *,
        customer_id: str,
    ) -> CustomerIdentity | None:
        self._require_ready()

        normalized_customer_id = (
            self._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        return self._customers.get(
            normalized_customer_id
        )

    def contains(
        self,
        *,
        customer_id: str,
    ) -> bool:
        return (
            self.get(
                customer_id=customer_id
            )
            is not None
        )

    def all(
        self,
    ) -> tuple[
        CustomerIdentity,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._customers[
                customer_id
            ]
            for customer_id in sorted(
                self._customers
            )
        )

    def size(
        self,
    ) -> int:
        self._require_ready()

        return len(
            self._customers
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer identity registry is not "
                "initialized."
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
                "Customer identity payload must "
                "be an object."
            )

        if set(
            payload
        ) != {
            "version",
            "customers",
        }:
            raise ValueError(
                "Customer identity payload has "
                "invalid fields."
            )

        if payload.get(
            "version"
        ) != STORE_VERSION:
            raise ValueError(
                "Unsupported customer identity "
                "registry version."
            )

        items = payload.get(
            "customers"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer identity records must "
                "be a list."
            )

        restored: dict[
            str,
            CustomerIdentity,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer identity item must "
                    "be an object."
                )

            if set(
                item
            ) != {
                "customer_id",
            }:
                raise ValueError(
                    "Customer identity item has "
                    "invalid fields."
                )

            identity = CustomerIdentity(
                customer_id=item[
                    "customer_id"
                ]
            )

            if (
                identity.customer_id
                in restored
            ):
                raise ValueError(
                    "Duplicate customer identity."
                )

            restored[
                identity.customer_id
            ] = identity

        self._customers = restored
        self._ready = True

    def _write_customers(
        self,
        customers: dict[
            str,
            CustomerIdentity,
        ],
    ) -> None:
        items = []

        for customer_id in sorted(
            customers
        ):
            identity = customers[
                customer_id
            ]

            items.append(
                {
                    "customer_id": (
                        identity.customer_id
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "customers": items,
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
