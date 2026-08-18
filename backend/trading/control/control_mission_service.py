"""
TODOBA Control Mission Service

Coordinates control mission creation flow.

This component owns:
- repository storage
- mission persistence
- lifecycle registration
- queue transition
- delivery to the Trusted Agent queue
- producer retry safety
- optional Cloud-owned security sequence assignment

It does not:
- receive HTTP requests
- execute broker control actions
"""

from dataclasses import replace
from typing import Optional

from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_delivery_bridge import (
    ControlMissionDeliveryBridge,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
)
from backend.trading.control.control_mission_persistence import (
    ControlMissionPersistence,
)
from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
)
from backend.trading.control.control_mission_serializer import (
    ControlMissionSerializer,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)
from backend.trading.execution.security_sequence_assignment_service import (
    SecuritySequenceAssignmentService,
)


class ControlMissionService:
    """
    Application service for control mission creation.
    """

    _TERMINAL_STATUSES = {
        ControlMissionStatus.COMPLETED,
        ControlMissionStatus.FAILED,
    }

    def __init__(
        self,
        repository: ControlMissionRepository,
        persistence: ControlMissionPersistence,
        delivery_bridge: ControlMissionDeliveryBridge,
        registry: ControlMissionRegistry,
        lifecycle_service: ControlMissionLifecycleService,
        *,
        security_sequence_assignment_service: Optional[
            SecuritySequenceAssignmentService
        ] = None,
    ) -> None:
        if not isinstance(
            repository,
            ControlMissionRepository,
        ):
            raise TypeError(
                "ControlMissionService requires "
                "ControlMissionRepository."
            )

        if not isinstance(
            persistence,
            ControlMissionPersistence,
        ):
            raise TypeError(
                "ControlMissionService requires "
                "ControlMissionPersistence."
            )

        if not isinstance(
            delivery_bridge,
            ControlMissionDeliveryBridge,
        ):
            raise TypeError(
                "ControlMissionService requires "
                "ControlMissionDeliveryBridge."
            )

        if not isinstance(
            registry,
            ControlMissionRegistry,
        ):
            raise TypeError(
                "ControlMissionService requires "
                "ControlMissionRegistry."
            )

        if not isinstance(
            lifecycle_service,
            ControlMissionLifecycleService,
        ):
            raise TypeError(
                "ControlMissionService requires "
                "ControlMissionLifecycleService."
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
        self.lifecycle_service = lifecycle_service
        self.security_sequence_assignment_service = (
            security_sequence_assignment_service
        )

    def _assign_security_sequence(
        self,
        mission: ControlMission,
    ) -> ControlMission:
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
            ControlMissionSerializer.serialize(
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
        mission: ControlMission,
    ) -> ControlMission:
        if not isinstance(
            mission,
            ControlMission,
        ):
            raise TypeError(
                "create_mission requires ControlMission."
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
                "Control mission ID conflict."
            )

        if (
            existing_record is not None
            and existing_record.status
            in self._TERMINAL_STATUSES
        ):
            return existing_record.mission

        stored_mission = self.repository.save(
            final_mission
        )

        self.persistence.save(
            self.repository
        )

        record = existing_record

        if record is None:
            record = self.registry.register(
                ControlMissionRecord(
                    mission=stored_mission
                )
            )

        if record.status == ControlMissionStatus.CREATED:
            record = self.lifecycle_service.queue(
                stored_mission.mission_id
            )

        if record.status == ControlMissionStatus.QUEUED:
            self.delivery_bridge.deliver(
                stored_mission
            )

        return stored_mission