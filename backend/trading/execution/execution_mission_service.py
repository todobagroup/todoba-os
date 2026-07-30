"""
TODOBA Execution Mission Service

Coordinates execution mission creation flow.

This component owns:
- repository storage
- persistence
- lifecycle registration
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

from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
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
        registry: ExecutionMissionRegistry,
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

        if not isinstance(
            registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "ExecutionMissionService requires "
                "ExecutionMissionRegistry."
            )

        self.repository = repository
        self.persistence = persistence
        self.delivery_bridge = delivery_bridge
        self.registry = registry

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

        record = ExecutionMissionRecord(
            mission=mission
        )

        self.registry.register(
            record
        )

        self.delivery_bridge.deliver(
            mission
        )

        return mission