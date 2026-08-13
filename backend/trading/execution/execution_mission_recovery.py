"""
TODOBA Execution Mission Recovery

Restores eligible execution missions after runtime restart.

Responsibilities:

- restore persisted missions
- verify lifecycle record ownership
- remove orphaned missions
- remove terminal FAILED and COMPLETED missions
- persist recovery cleanup
- redeliver only eligible missions

This component does not:

- receive HTTP requests
- execute broker orders
- manage MT5
"""

from typing import Optional

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


class ExecutionMissionRecovery:
    """
    Recovery lifecycle for persisted execution missions.
    """

    def __init__(
        self,
        *,
        repository: ExecutionMissionRepository,
        persistence: ExecutionMissionPersistence,
        delivery_bridge: ExecutionMissionDeliveryBridge,
        registry: Optional[
            ExecutionMissionRegistry
        ] = None,
    ) -> None:
        if not isinstance(
            repository,
            ExecutionMissionRepository,
        ):
            raise TypeError(
                "ExecutionMissionRecovery requires "
                "ExecutionMissionRepository."
            )

        if not isinstance(
            persistence,
            ExecutionMissionPersistence,
        ):
            raise TypeError(
                "ExecutionMissionRecovery requires "
                "ExecutionMissionPersistence."
            )

        if not isinstance(
            delivery_bridge,
            ExecutionMissionDeliveryBridge,
        ):
            raise TypeError(
                "ExecutionMissionRecovery requires "
                "ExecutionMissionDeliveryBridge."
            )

        if (
            registry is not None
            and not isinstance(
                registry,
                ExecutionMissionRegistry,
            )
        ):
            raise TypeError(
                "registry must be "
                "ExecutionMissionRegistry."
            )

        self.repository = repository
        self.persistence = persistence
        self.delivery_bridge = delivery_bridge
        self.registry = registry

    def restore(
        self,
    ) -> int:
        """
        Restore persisted missions and redeliver only
        missions that remain lifecycle eligible.
        """

        self.persistence.restore(
            self.repository
        )

        restored = 0
        repository_changed = False

        for mission in self.repository.all():
            if self._must_remove(
                mission
            ):
                removed = self.repository.remove(
                    mission.mission_id
                )

                if removed:
                    repository_changed = True

                continue

            self.delivery_bridge.deliver(
                mission
            )

            restored += 1

        if repository_changed:
            self.persistence.save(
                self.repository
            )

        return restored

    def _must_remove(
        self,
        mission: ExecutionMission,
    ) -> bool:
        if self.registry is None:
            return False

        record = self.registry.get(
            mission.mission_id
        )

        if record is None:
            return True

        return record.status in {
            ExecutionMissionStatus.FAILED,
            ExecutionMissionStatus.COMPLETED,
        }