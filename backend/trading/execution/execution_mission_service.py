"""
TODOBA Execution Mission Service

Coordinates execution mission creation flow.

This component owns:
- repository storage
- mission persistence
- lifecycle registration
- mission record persistence
- initial delivery to Trusted Agent queue
- producer retry safety
- optional Cloud-owned security sequence assignment

It does not:
- receive HTTP requests
- execute broker orders
- own lease-based redelivery policy
"""

from dataclasses import replace
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
from backend.trading.execution.execution_mission_serializer import (
    ExecutionMissionSerializer,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)
from backend.trading.execution.security_sequence_assignment_service import (
    SecuritySequenceAssignmentService,
)


class ExecutionMissionService:
    """
    Application service for execution mission creation.
    """

    _TERMINAL_STATUSES = {
        ExecutionMissionStatus.COMPLETED,
        ExecutionMissionStatus.FAILED,
    }

    def __init__(
        self,
        repository: ExecutionMissionRepository,
        persistence: ExecutionMissionPersistence,
        delivery_bridge: ExecutionMissionDeliveryBridge,
        registry: ExecutionMissionRegistry,
        record_persistence: Optional[
            ExecutionMissionRecordPersistence
        ] = None,
        *,
        security_sequence_assignment_service: Optional[
            SecuritySequenceAssignmentService
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

        if (
            security_sequence_assignment_service
            is not None
            and not isinstance(
                security_sequence_assignment_service,
                SecuritySequenceAssignmentService,
            )
        ):
            raise TypeError(
                "security_sequence_assignment_service "
                "must be SecuritySequenceAssignmentService."
            )

        self.repository = repository
        self.persistence = persistence
        self.delivery_bridge = delivery_bridge
        self.registry = registry
        self.record_persistence = record_persistence
        self.security_sequence_assignment_service = (
            security_sequence_assignment_service
        )

    def _assign_security_sequence(
        self,
        mission: ExecutionMission,
    ) -> ExecutionMission:
        assignment_service = (
            self.security_sequence_assignment_service
        )

        if assignment_service is None:
            return mission

        if mission.security_sequence != 0:
            raise ValueError(
                "source mission security_sequence "
                "must be zero."
            )

        source_payload = (
            ExecutionMissionSerializer.serialize(
                mission
            )
        )

        security_sequence = (
            assignment_service.assign(
                mission_id=mission.mission_id,
                source_payload=source_payload,
            )
        )

        return replace(
            mission,
            security_sequence=security_sequence,
        )

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

        final_mission = self._assign_security_sequence(
            mission
        )

        existing_record = self.registry.get(
            final_mission.mission_id
        )

        if (
            existing_record is not None
            and existing_record.mission != final_mission
        ):
            raise ValueError(
                "Execution mission ID conflict."
            )

        if existing_record is not None:
            if (
                existing_record.status
                in self._TERMINAL_STATUSES
            ):
                return existing_record.mission

            if (
                existing_record.status
                != ExecutionMissionStatus.CREATED
            ):
                return existing_record.mission

            stored_mission = self.repository.save(
                final_mission
            )

            self.persistence.save(
                self.repository
            )

            self.delivery_bridge.redeliver(
                stored_mission
            )

            return stored_mission

        stored_mission = self.repository.save(
            final_mission
        )

        self.persistence.save(
            self.repository
        )

        record = self.registry.register(
            ExecutionMissionRecord(
                mission=stored_mission
            )
        )

        if self.record_persistence is not None:
            self.record_persistence.save(
                self.registry
            )

        self.delivery_bridge.deliver(
            stored_mission
        )

        return record.mission