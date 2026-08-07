"""
TODOBA Execution Mission Delivery Redelivery Processor

Redelivers execution missions whose delivery leases
have expired before acknowledgement.

Responsibilities:
- inspect active delivery leases
- detect expired leases
- recover the original execution mission
- redeliver the mission
- release the expired lease after successful redelivery

This component does not:
- receive HTTP requests
- acknowledge missions
- persist leases
- execute broker orders
"""

from datetime import datetime
from datetime import timezone
from typing import Callable

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)


def utc_now() -> datetime:
    """
    Return the current timezone-aware UTC datetime.
    """

    return datetime.now(
        timezone.utc
    )


class ExecutionMissionDeliveryRedeliveryProcessor:
    """
    Redelivers one expired execution mission lease.
    """

    def __init__(
        self,
        *,
        repository: ExecutionMissionRepository,
        delivery_bridge: ExecutionMissionDeliveryBridge,
        lease_registry: ExecutionMissionDeliveryLeaseRegistry,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not isinstance(
            repository,
            ExecutionMissionRepository,
        ):
            raise TypeError(
                "ExecutionMissionDeliveryRedeliveryProcessor "
                "requires ExecutionMissionRepository."
            )

        if not isinstance(
            delivery_bridge,
            ExecutionMissionDeliveryBridge,
        ):
            raise TypeError(
                "ExecutionMissionDeliveryRedeliveryProcessor "
                "requires ExecutionMissionDeliveryBridge."
            )

        if not isinstance(
            lease_registry,
            ExecutionMissionDeliveryLeaseRegistry,
        ):
            raise TypeError(
                "ExecutionMissionDeliveryRedeliveryProcessor "
                "requires "
                "ExecutionMissionDeliveryLeaseRegistry."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self.repository = repository
        self.delivery_bridge = delivery_bridge
        self.lease_registry = lease_registry
        self.clock = clock

    def process_next(
        self,
    ) -> ExecutionMission | None:
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

        for lease in self.lease_registry.list():
            if not self._is_expired(
                lease,
                now_utc,
            ):
                continue

            mission = self.repository.get(
                lease.mission_id
            )

            if mission is None:
                raise ValueError(
                    "Execution mission not found for redelivery."
                )

            result = self.delivery_bridge.deliver(
                mission
            )

            self.lease_registry.release(
                lease.mission_id
            )

            return result

        return None

    @staticmethod
    def _is_expired(
        lease: ExecutionMissionDeliveryLease,
        now: datetime,
    ) -> bool:
        expires_at = datetime.fromisoformat(
            lease.expires_at.replace(
                "Z",
                "+00:00",
            )
        )

        if (
            expires_at.tzinfo is None
            or expires_at.utcoffset() is None
        ):
            raise ValueError(
                "lease expires_at must be timezone-aware."
            )

        return (
            expires_at.astimezone(
                timezone.utc
            )
            <= now
        )