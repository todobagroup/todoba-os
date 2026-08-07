"""
TODOBA Execution Mission Delivery Lease Service

Creates temporary delivery leases for execution missions.

Responsibilities:
- create UTC lease timestamps
- calculate lease expiration
- acquire leases through the lease registry

This component does not:
- deliver missions
- acknowledge missions
- retry missions
- persist leases
- receive HTTP requests
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Callable

from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)


def utc_now() -> datetime:
    """
    Return the current timezone-aware UTC datetime.
    """

    return datetime.now(
        timezone.utc
    )


class ExecutionMissionDeliveryLeaseService:
    """
    Creates and acquires execution mission delivery leases.
    """

    def __init__(
        self,
        *,
        registry: ExecutionMissionDeliveryLeaseRegistry,
        lease_seconds: float,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(
            registry,
            ExecutionMissionDeliveryLeaseRegistry,
        ):
            raise TypeError(
                "ExecutionMissionDeliveryLeaseService "
                "requires "
                "ExecutionMissionDeliveryLeaseRegistry."
            )

        if not isinstance(
            lease_seconds,
            (int, float),
        ):
            raise TypeError(
                "lease_seconds must be numeric."
            )

        if lease_seconds <= 0:
            raise ValueError(
                "lease_seconds must be greater than zero."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self.registry = registry

        self.lease_seconds = float(
            lease_seconds
        )

        self.clock = clock

    def acquire(
        self,
        *,
        mission_id: str,
        agent_id: str,
    ) -> ExecutionMissionDeliveryLease:
        now = self.clock()

        if not isinstance(
            now,
            datetime,
        ):
            raise TypeError(
                "clock must return datetime."
            )

        if (
            now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError(
                "clock must return timezone-aware datetime."
            )

        now_utc = now.astimezone(
            timezone.utc
        )

        expires_at = (
            now_utc
            + timedelta(
                seconds=self.lease_seconds
            )
        )

        lease = ExecutionMissionDeliveryLease(
            mission_id=mission_id,
            agent_id=agent_id,
            leased_at=self._serialize_utc(
                now_utc
            ),
            expires_at=self._serialize_utc(
                expires_at
            ),
        )

        return self.registry.acquire(
            lease
        )

    @staticmethod
    def _serialize_utc(
        value: datetime,
    ) -> str:
        return (
            value.astimezone(
                timezone.utc
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )