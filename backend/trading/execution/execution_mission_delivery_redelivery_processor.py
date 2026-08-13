"""
TODOBA Execution Mission Delivery Redelivery Processor

Redelivers execution missions whose delivery leases
have expired before acknowledgement.

Responsibilities:

- inspect active delivery leases
- detect expired leases
- release orphaned leases safely
- enforce bounded delivery attempts
- recover the original execution mission
- redeliver the mission when attempts remain
- fail the mission when attempts are exhausted
- persist remaining delivery leases

This component does not:

- receive HTTP requests
- acknowledge missions
- execute broker orders
"""

from datetime import datetime
from datetime import timezone
from typing import Callable
from typing import Optional

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)


def utc_now() -> datetime:
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
        lease_persistence: Optional[
            ExecutionMissionDeliveryLeasePersistence
        ] = None,
        lifecycle_service: Optional[
            ExecutionMissionLifecycleService
        ] = None,
        max_delivery_attempts: int = 3,
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

        if (
            lease_persistence is not None
            and not isinstance(
                lease_persistence,
                ExecutionMissionDeliveryLeasePersistence,
            )
        ):
            raise TypeError(
                "lease_persistence must be "
                "ExecutionMissionDeliveryLeasePersistence."
            )

        if (
            lifecycle_service is not None
            and not isinstance(
                lifecycle_service,
                ExecutionMissionLifecycleService,
            )
        ):
            raise TypeError(
                "lifecycle_service must be "
                "ExecutionMissionLifecycleService."
            )

        if (
            not isinstance(
                max_delivery_attempts,
                int,
            )
            or isinstance(
                max_delivery_attempts,
                bool,
            )
            or max_delivery_attempts <= 0
        ):
            raise ValueError(
                "max_delivery_attempts must be "
                "a positive integer."
            )

        self.repository = repository
        self.delivery_bridge = delivery_bridge
        self.lease_registry = lease_registry
        self.clock = clock
        self.lease_persistence = lease_persistence
        self.lifecycle_service = lifecycle_service
        self.max_delivery_attempts = (
            max_delivery_attempts
        )

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
                self._release_lease(
                    lease.mission_id
                )

                return None

            if self._delivery_attempts_exhausted(
                mission.mission_id
            ):
                self._fail_exhausted_mission(
                    mission_id=mission.mission_id,
                    failed_at=self._format_datetime(
                        now_utc
                    ),
                )

                self._release_lease(
                    mission.mission_id
                )

                return None

            result = self.delivery_bridge.deliver(
                mission
            )

            self._release_lease(
                lease.mission_id
            )

            return result

        return None

    def _delivery_attempts_exhausted(
        self,
        mission_id: str,
    ) -> bool:
        if self.lifecycle_service is None:
            return False

        record = self.lifecycle_service.registry.get(
            mission_id
        )

        if record is None:
            raise ValueError(
                "Execution mission record not found."
            )

        return (
            record.delivery_attempt_count
            >= self.max_delivery_attempts
        )

    def _fail_exhausted_mission(
        self,
        *,
        mission_id: str,
        failed_at: str,
    ) -> None:
        if self.lifecycle_service is None:
            return

        self.lifecycle_service.fail_execution(
            mission_id=mission_id,
            failed_at=failed_at,
            failure_reason=(
                "Delivery attempts exhausted."
            ),
        )

    def _release_lease(
        self,
        mission_id: str,
    ) -> None:
        released = self.lease_registry.release(
            mission_id
        )

        if (
            released is not None
            and self.lease_persistence is not None
        ):
            self.lease_persistence.save(
                self.lease_registry
            )

    @staticmethod
    def _format_datetime(
        value: datetime,
    ) -> str:
        return (
            value.astimezone(
                timezone.utc
            )
            .isoformat(
                timespec="seconds"
            )
            .replace(
                "+00:00",
                "Z",
            )
        )

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