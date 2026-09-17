"""
TODOBA Customer Commercial FX Freshness Gate.

Consumes the latest authoritative USD/VND FX snapshot and
decides whether that snapshot is currently usable.

Freshness authority:

    age = trusted current time - snapshot.published_at

Important:

- published_at is authoritative provider time.
- fetched_at is observation metadata and MUST NOT refresh age.
- future-dated provider truth fails closed.
- max_age is injected policy; this owner does not define the
  production TTL.
- this owner is read-only and does not fetch, refresh, price,
  create orders, verify payments, settle, or grant entitlement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from backend.commercial.customer_commercial_fx_snapshot_service import (
    CustomerCommercialFXSnapshotRecord,
    CustomerCommercialFXSnapshotStore,
)


@dataclass(
    frozen=True,
)
class CustomerCommercialFXFreshnessResult:
    """
    Narrow result of one authoritative FX freshness decision.
    """

    status: Literal[
        "usable",
        "stale",
        "unavailable",
    ]

    snapshot: (
        CustomerCommercialFXSnapshotRecord
        | None
    )

    age: timedelta | None

    def __post_init__(
        self,
    ) -> None:
        if self.status not in (
            "usable",
            "stale",
            "unavailable",
        ):
            raise ValueError(
                "Unsupported FX freshness status."
            )

        if self.status == "unavailable":
            if (
                self.snapshot is not None
                or self.age is not None
            ):
                raise ValueError(
                    "Unavailable FX freshness result "
                    "cannot contain snapshot or age."
                )

            return

        if not isinstance(
            self.snapshot,
            CustomerCommercialFXSnapshotRecord,
        ):
            raise TypeError(
                "Usable/stale FX freshness result "
                "requires authoritative snapshot."
            )

        if not isinstance(
            self.age,
            timedelta,
        ):
            raise TypeError(
                "Usable/stale FX freshness result "
                "requires timedelta age."
            )


class CustomerCommercialFXFreshnessGate:
    """
    Last-known-good authoritative FX usability gate.
    """

    def __init__(
        self,
        *,
        snapshot_store: CustomerCommercialFXSnapshotStore,
        source_id: str,
        max_age: timedelta,
        clock: Callable[
            [],
            datetime,
        ],
    ) -> None:
        if not isinstance(
            snapshot_store,
            CustomerCommercialFXSnapshotStore,
        ):
            raise TypeError(
                "snapshot_store must be "
                "CustomerCommercialFXSnapshotStore."
            )

        if not isinstance(
            source_id,
            str,
        ):
            raise TypeError(
                "source_id must be str."
            )

        normalized_source = (
            source_id.strip()
        )

        if not normalized_source:
            raise ValueError(
                "source_id must not be empty."
            )

        if not isinstance(
            max_age,
            timedelta,
        ):
            raise TypeError(
                "max_age must be timedelta."
            )

        if max_age <= timedelta(0):
            raise ValueError(
                "max_age must be greater than zero."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        if not snapshot_store.is_ready():
            raise RuntimeError(
                "Commercial FX snapshot store "
                "must be initialized."
            )

        self._snapshot_store = (
            snapshot_store
        )

        self._source_id = (
            normalized_source
        )

        self._max_age = max_age
        self._clock = clock

    def evaluate(
        self,
    ) -> CustomerCommercialFXFreshnessResult:
        """
        Evaluate latest authoritative FX truth without mutation.
        """

        latest = (
            self._snapshot_store.latest(
                source_id=self._source_id,
                base_currency="USD",
                quote_currency="VND",
            )
        )

        if latest is None:
            return CustomerCommercialFXFreshnessResult(
                status="unavailable",
                snapshot=None,
                age=None,
            )

        current_time = (
            self._read_clock()
        )

        age = (
            current_time
            - latest.published_at
        )

        if age < timedelta(0):
            return CustomerCommercialFXFreshnessResult(
                status="stale",
                snapshot=latest,
                age=age,
            )

        if age > self._max_age:
            return CustomerCommercialFXFreshnessResult(
                status="stale",
                snapshot=latest,
                age=age,
            )

        return CustomerCommercialFXFreshnessResult(
            status="usable",
            snapshot=latest,
            age=age,
        )

    def require_usable(
        self,
    ) -> CustomerCommercialFXSnapshotRecord:
        """
        Return authoritative FX truth only when currently usable.
        """

        result = self.evaluate()

        if (
            result.status != "usable"
            or result.snapshot is None
        ):
            raise RuntimeError(
                "FX snapshot is not currently usable."
            )

        return result.snapshot

    def _read_clock(
        self,
    ) -> datetime:
        value = self._clock()

        if not isinstance(
            value,
            datetime,
        ):
            raise RuntimeError(
                "FX freshness clock must return "
                "timezone-aware datetime."
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise RuntimeError(
                "FX freshness clock must return "
                "timezone-aware datetime."
            )

        return value.astimezone(
            UTC
        )
