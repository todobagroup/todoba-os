"""
TODOBA Control Mission Service

Coordinates control mission creation flow.

This component owns:
- repository storage
- mission persistence
- lifecycle registration
- queue transition
- delivery to the Trusted Agent queue

It does not:
- receive HTTP requests
- execute broker control actions
"""

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
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
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

        self.repository = repository
        self.persistence = persistence
        self.delivery_bridge = delivery_bridge
        self.registry = registry
        self.lifecycle_service = lifecycle_service

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

        existing_record = self.registry.get(
            mission.mission_id
        )

        if (
            existing_record is not None
            and existing_record.mission != mission
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
            mission
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