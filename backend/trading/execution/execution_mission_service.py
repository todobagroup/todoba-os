"""
TODOBA Execution Mission Service

Coordinates execution mission creation flow.

This component owns:
- repository storage
- persistence
- delivery to Trusted Agent queue

It does not:
- receive HTTP requests
- execute broker orders
"""

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)

from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)

from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)


class ExecutionMissionService:
    """
    Application service for execution mission lifecycle.
    """

    def __init__(
        self,
        repository: ExecutionMissionRepository,
        persistence: ExecutionMissionPersistence,
        delivery_bridge: ExecutionMissionDeliveryBridge,
    ) -> None:

        if not isinstance(
            repository,
            ExecutionMissionRepository,
        ):
            raise TypeError(
                "ExecutionMissionService requires "
                "ExecutionMissionRepository."
            )

        if not isinstance(
            persistence,
            ExecutionMissionPersistence,
        ):
            raise TypeError(
                "ExecutionMissionService requires "
                "ExecutionMissionPersistence."
            )

        if not isinstance(
            delivery_bridge,
            ExecutionMissionDeliveryBridge,
        ):
            raise TypeError(
                "ExecutionMissionService requires "
                "ExecutionMissionDeliveryBridge."
            )

        self.repository = repository
        self.persistence = persistence
        self.delivery_bridge = delivery_bridge

    def create_mission(
        self,
        mission: ExecutionMission,
    ) -> ExecutionMission:

        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "create_mission requires ExecutionMission."
            )

        self.repository.save(
            mission
        )

        self.persistence.save(
            self.repository
        )

        self.delivery_bridge.deliver(
            mission
        )

        return mission