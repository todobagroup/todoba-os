"""
TODOBA Execution Mission Delivery Lease Service

Creates and persists temporary delivery leases
for execution missions.
"""

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)


def utc_now() -> datetime:
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
        persistence: Optional[
            ExecutionMissionDeliveryLeasePersistence
        ] = None,
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

        if not callable(clock):
            raise TypeError(
                "clock must be callable."
            )

        if (
            persistence is not None
            and not isinstance(
                persistence,
                ExecutionMissionDeliveryLeasePersistence,
            )
        ):
            raise TypeError(
                "persistence must be "
                "ExecutionMissionDeliveryLeasePersistence."
            )

        self.registry = registry
        self.lease_seconds = float(
            lease_seconds
        )
        self.clock = clock
        self.persistence = persistence

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

        lease = ExecutionMissionDeliveryLease(
            mission_id=mission_id,
            agent_id=agent_id,
            leased_at=self._serialize_utc(
                now_utc
            ),
            expires_at=self._serialize_utc(
                now_utc
                + timedelta(
                    seconds=self.lease_seconds
                )
            ),
        )

        existing = self.registry.get(
            mission_id
        )

        acquired = self.registry.acquire(
            lease
        )

        if self.persistence is not None:
            try:
                self.persistence.save(
                    self.registry
                )
            except Exception:
                if existing is None:
                    self.registry.release(
                        mission_id
                    )
                raise

        return acquired

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