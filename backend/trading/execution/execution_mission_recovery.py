"""
TODOBA Execution Mission Recovery

Restores execution missions after runtime restart.

This component:

- restores missions from persistence
- verifies lifecycle record ownership
- moves valid restored missions back to delivery queue

It does not:

- receive HTTP requests
- execute broker orders
- manage MT5
"""

from typing import Optional

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


class ExecutionMissionRecovery:
    """
    Recovery lifecycle for execution missions.
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

    def restore(self) -> int:
        """
        Restore persisted missions and deliver only
        missions that still own lifecycle records.
        """

        self.persistence.restore(
            self.repository
        )

        restored = 0

        for mission in self.repository.all():
            if (
                self.registry is not None
                and self.registry.get(
                    mission.mission_id
                )
                is None
            ):
                continue

            self.delivery_bridge.deliver(
                mission
            )

            restored += 1

        return restored