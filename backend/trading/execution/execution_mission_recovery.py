"""
TODOBA Execution Mission Recovery

Restores execution missions after runtime restart.

This component:
- restores missions from persistence
- moves restored missions back to delivery queue

It does not:
- receive HTTP requests
- execute broker orders
- manage MT5
"""

from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)

from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)

from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
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

        self.repository = repository
        self.persistence = persistence
        self.delivery_bridge = delivery_bridge

    def restore(self) -> int:
        """
        Restore persisted missions and deliver them.
        """

        count = self.persistence.restore(
            self.repository
        )

        restored = 0

        for mission in self.repository.all():

            self.delivery_bridge.deliver(
                mission
            )

            restored += 1

        return restored