from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


_STORE_VERSION = 1


class CustomerCommercialEntitlementStatus(
    str,
    Enum,
):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


@dataclass(
    frozen=True,
)
class CustomerCommercialEntitlement:
    """
    Durable purchased commercial entitlement truth.

    The commercial facts are immutable after registration.
    Only entitlement status may transition between ACTIVE
    and SUSPENDED.

    This owner has no payment, settlement, Setup,
    deployment, MT5, runtime, or network authority.
    """

    entitlement_id: str
    order_id: str
    customer_id: str
    licensed_account_cap_usd: int
    standard_monthly_price_usd: int
    status: CustomerCommercialEntitlementStatus

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "entitlement_id",
            self._normalize_required_string(
                self.entitlement_id,
                name="entitlement_id",
            ),
        )
        object.__setattr__(
            self,
            "order_id",
            self._normalize_required_string(
                self.order_id,
                name="order_id",
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
            "licensed_account_cap_usd",
            self._normalize_positive_int(
                self.licensed_account_cap_usd,
                name="licensed_account_cap_usd",
            ),
        )
        object.__setattr__(
            self,
            "standard_monthly_price_usd",
            self._normalize_positive_int(
                self.standard_monthly_price_usd,
                name="standard_monthly_price_usd",
            ),
        )

        if not isinstance(
            self.status,
            CustomerCommercialEntitlementStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerCommercialEntitlementStatus."
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

    @staticmethod
    def _normalize_positive_int(
        value: int,
        *,
        name: str,
    ) -> int:
        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                f"{name} must be int."
            )

        if value <= 0:
            raise ValueError(
                f"{name} must be positive."
            )

        return value


class CustomerCommercialEntitlementRegistry:
    """
    Durable purchased commercial entitlement authority.

    Primary identity:
        entitlement_id

    Unique purchase identity:
        order_id
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
        self._entitlements: dict[
            str,
            CustomerCommercialEntitlement,
        ] = {}
        self._entitlement_id_by_order_id: dict[
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
            if self.storage_path.exists():
                raise RuntimeError(
                    "Commercial entitlement registry "
                    "already exists."
                )

            self.storage_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._persist(
                {}
            )

            self._entitlements = {}
            self._entitlement_id_by_order_id = {}
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if not self.storage_path.exists():
                raise RuntimeError(
                    "Commercial entitlement registry "
                    "does not exist."
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
            ) as exc:
                raise RuntimeError(
                    "Commercial entitlement registry "
                    "could not be opened."
                ) from exc

            if (
                not isinstance(
                    payload,
                    dict,
                )
                or set(
                    payload
                )
                != {
                    "version",
                    "entitlements",
                }
                or payload.get(
                    "version"
                )
                != _STORE_VERSION
                or not isinstance(
                    payload.get(
                        "entitlements"
                    ),
                    list,
                )
            ):
                raise RuntimeError(
                    "Commercial entitlement registry "
                    "payload is invalid."
                )

            restored: dict[
                str,
                CustomerCommercialEntitlement,
            ] = {}

            order_index: dict[
                str,
                str,
            ] = {}

            for raw in payload[
                "entitlements"
            ]:
                if (
                    not isinstance(
                        raw,
                        dict,
                    )
                    or set(
                        raw
                    )
                    != {
                        "entitlement_id",
                        "order_id",
                        "customer_id",
                        "licensed_account_cap_usd",
                        "standard_monthly_price_usd",
                        "status",
                    }
                ):
                    raise RuntimeError(
                        "Commercial entitlement record "
                        "payload is invalid."
                    )

                try:
                    entitlement = (
                        CustomerCommercialEntitlement(
                            entitlement_id=raw[
                                "entitlement_id"
                            ],
                            order_id=raw[
                                "order_id"
                            ],
                            customer_id=raw[
                                "customer_id"
                            ],
                            licensed_account_cap_usd=raw[
                                "licensed_account_cap_usd"
                            ],
                            standard_monthly_price_usd=raw[
                                "standard_monthly_price_usd"
                            ],
                            status=(
                                CustomerCommercialEntitlementStatus(
                                    raw[
                                        "status"
                                    ]
                                )
                            ),
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ) as exc:
                    raise RuntimeError(
                        "Commercial entitlement record "
                        "payload is invalid."
                    ) from exc

                if (
                    entitlement.entitlement_id
                    in restored
                ):
                    raise RuntimeError(
                        "Duplicate commercial entitlement ID."
                    )

                if (
                    entitlement.order_id
                    in order_index
                ):
                    raise RuntimeError(
                        "Duplicate commercial entitlement order."
                    )

                restored[
                    entitlement.entitlement_id
                ] = entitlement

                order_index[
                    entitlement.order_id
                ] = entitlement.entitlement_id

            self._entitlements = restored
            self._entitlement_id_by_order_id = (
                order_index
            )
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        with self._lock:
            return self._ready

    def register(
        self,
        entitlement: CustomerCommercialEntitlement,
    ) -> CustomerCommercialEntitlement:
        if not isinstance(
            entitlement,
            CustomerCommercialEntitlement,
        ):
            raise TypeError(
                "Commercial entitlement registry "
                "requires CustomerCommercialEntitlement."
            )

        with self._lock:
            self._require_ready()

            existing = self._entitlements.get(
                entitlement.entitlement_id
            )

            if existing is not None:
                if existing != entitlement:
                    raise ValueError(
                        "entitlement is already bound "
                        "to different commercial truth."
                    )

                return existing

            existing_entitlement_id = (
                self._entitlement_id_by_order_id.get(
                    entitlement.order_id
                )
            )

            if existing_entitlement_id is not None:
                raise ValueError(
                    "order is already bound "
                    "to a commercial entitlement."
                )

            candidate = dict(
                self._entitlements
            )
            candidate[
                entitlement.entitlement_id
            ] = entitlement

            self._persist(
                candidate
            )

            order_index = dict(
                self._entitlement_id_by_order_id
            )
            order_index[
                entitlement.order_id
            ] = entitlement.entitlement_id

            self._entitlements = candidate
            self._entitlement_id_by_order_id = (
                order_index
            )

            return entitlement

    def get(
        self,
        *,
        entitlement_id: str,
    ) -> CustomerCommercialEntitlement | None:
        normalized = (
            CustomerCommercialEntitlement
            ._normalize_required_string(
                entitlement_id,
                name="entitlement_id",
            )
        )

        with self._lock:
            self._require_ready()

            return self._entitlements.get(
                normalized
            )

    def get_by_order_id(
        self,
        *,
        order_id: str,
    ) -> CustomerCommercialEntitlement | None:
        normalized = (
            CustomerCommercialEntitlement
            ._normalize_required_string(
                order_id,
                name="order_id",
            )
        )

        with self._lock:
            self._require_ready()

            entitlement_id = (
                self._entitlement_id_by_order_id.get(
                    normalized
                )
            )

            if entitlement_id is None:
                return None

            return self._entitlements[
                entitlement_id
            ]

    def is_active(
        self,
        *,
        entitlement_id: str,
    ) -> bool:
        try:
            entitlement = self.get(
                entitlement_id=entitlement_id
            )
        except (
            TypeError,
            ValueError,
        ):
            return False

        return (
            entitlement is not None
            and entitlement.status
            is CustomerCommercialEntitlementStatus.ACTIVE
        )

    def suspend(
        self,
        *,
        entitlement_id: str,
    ) -> CustomerCommercialEntitlement:
        return self._change_status(
            entitlement_id=entitlement_id,
            status=(
                CustomerCommercialEntitlementStatus.SUSPENDED
            ),
        )

    def activate(
        self,
        *,
        entitlement_id: str,
    ) -> CustomerCommercialEntitlement:
        return self._change_status(
            entitlement_id=entitlement_id,
            status=(
                CustomerCommercialEntitlementStatus.ACTIVE
            ),
        )

    def all(
        self,
    ) -> tuple[
        CustomerCommercialEntitlement,
        ...,
    ]:
        with self._lock:
            self._require_ready()

            return tuple(
                self._entitlements[
                    entitlement_id
                ]
                for entitlement_id in sorted(
                    self._entitlements
                )
            )

    def size(
        self,
    ) -> int:
        with self._lock:
            self._require_ready()

            return len(
                self._entitlements
            )

    def _change_status(
        self,
        *,
        entitlement_id: str,
        status: CustomerCommercialEntitlementStatus,
    ) -> CustomerCommercialEntitlement:
        normalized = (
            CustomerCommercialEntitlement
            ._normalize_required_string(
                entitlement_id,
                name="entitlement_id",
            )
        )

        with self._lock:
            self._require_ready()

            existing = self._entitlements.get(
                normalized
            )

            if existing is None:
                raise ValueError(
                    "commercial entitlement "
                    "is not authoritative."
                )

            if existing.status is status:
                return existing

            updated = (
                CustomerCommercialEntitlement(
                    entitlement_id=(
                        existing.entitlement_id
                    ),
                    order_id=(
                        existing.order_id
                    ),
                    customer_id=(
                        existing.customer_id
                    ),
                    licensed_account_cap_usd=(
                        existing.licensed_account_cap_usd
                    ),
                    standard_monthly_price_usd=(
                        existing.standard_monthly_price_usd
                    ),
                    status=status,
                )
            )

            candidate = dict(
                self._entitlements
            )
            candidate[
                existing.entitlement_id
            ] = updated

            self._persist(
                candidate
            )

            self._entitlements = candidate

            return updated

    def _persist(
        self,
        entitlements: dict[
            str,
            CustomerCommercialEntitlement,
        ],
    ) -> None:
        payload = {
            "version": _STORE_VERSION,
            "entitlements": [
                {
                    "entitlement_id": (
                        entitlements[
                            entitlement_id
                        ].entitlement_id
                    ),
                    "order_id": (
                        entitlements[
                            entitlement_id
                        ].order_id
                    ),
                    "customer_id": (
                        entitlements[
                            entitlement_id
                        ].customer_id
                    ),
                    "licensed_account_cap_usd": (
                        entitlements[
                            entitlement_id
                        ].licensed_account_cap_usd
                    ),
                    "standard_monthly_price_usd": (
                        entitlements[
                            entitlement_id
                        ].standard_monthly_price_usd
                    ),
                    "status": (
                        entitlements[
                            entitlement_id
                        ].status.value
                    ),
                }
                for entitlement_id in sorted(
                    entitlements
                )
            ],
        }

        encoded = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )

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
                newline="\n",
            ) as handle:
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
        except OSError as exc:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise RuntimeError(
                "Commercial entitlement registry "
                "could not be persisted."
            ) from exc

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Commercial entitlement registry "
                "is not initialized."
            )
