"""
TODOBA Execution Mission Service

Coordinates execution mission creation flow.

This component owns:
- repository storage
- mission persistence
- lifecycle registration
- mission record persistence
- delivery to Trusted Agent queue

It does not:
- receive HTTP requests
- execute broker orders
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
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)


class ExecutionMissionService:
    """
    Application service for execution mission creation.
    """

    def __init__(
        self,
        repository: ExecutionMissionRepository,
        persistence: ExecutionMissionPersistence,
        delivery_bridge: ExecutionMissionDeliveryBridge,
        registry: ExecutionMissionRegistry,
        record_persistence: Optional[
            ExecutionMissionRecordPersistence
        ] = None,
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

        if (
            record_persistence is not None
            and not isinstance(
                record_persistence,
                ExecutionMissionRecordPersistence,
            )
        ):
            raise TypeError(
                "record_persistence must be "
                "ExecutionMissionRecordPersistence."
            )

        self.repository = repository
        self.persistence = persistence
        self.delivery_bridge = delivery_bridge
        self.registry = registry
        self.record_persistence = record_persistence

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

        if self.record_persistence is not None:
            self.record_persistence.save(
                self.registry
            )

        self.delivery_bridge.deliver(
            mission
        )

        return mission