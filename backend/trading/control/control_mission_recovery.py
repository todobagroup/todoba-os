"""
TODOBA Control Mission Recovery

Restores eligible control missions after runtime restart.

Responsibilities:

- restore persisted control missions
- verify lifecycle record ownership
- remove orphaned missions
- remove terminal FAILED and COMPLETED missions
- persist recovery cleanup
- redeliver only eligible missions

This component does not:

- receive HTTP requests
- execute broker control actions
- communicate directly with MT5
"""

from typing import Optional

from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_delivery_bridge import (
    ControlMissionDeliveryBridge,
)
from backend.trading.control.control_mission_persistence import (
    ControlMissionPersistence,
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


class ControlMissionRecovery:
    """
    Recovery lifecycle for persisted control missions.
    """

    def __init__(
        self,
        *,
        repository: ControlMissionRepository,
        persistence: ControlMissionPersistence,
        delivery_bridge: ControlMissionDeliveryBridge,
        registry: Optional[
            ControlMissionRegistry
        ] = None,
    ) -> None:
        if not isinstance(
            repository,
            ControlMissionRepository,
        ):
            raise TypeError(
                "ControlMissionRecovery requires "
                "ControlMissionRepository."
            )

        if not isinstance(
            persistence,
            ControlMissionPersistence,
        ):
            raise TypeError(
                "ControlMissionRecovery requires "
                "ControlMissionPersistence."
            )

        if not isinstance(
            delivery_bridge,
            ControlMissionDeliveryBridge,
        ):
            raise TypeError(
                "ControlMissionRecovery requires "
                "ControlMissionDeliveryBridge."
            )

        if (
            registry is not None
            and not isinstance(
                registry,
                ControlMissionRegistry,
            )
        ):
            raise TypeError(
                "registry must be "
                "ControlMissionRegistry."
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

        restored_count = 0
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

            restored_count += 1

        if repository_changed:
            self.persistence.save(
                self.repository
            )

        return restored_count

    def _must_remove(
        self,
        mission: ControlMission,
    ) -> bool:
        if self.registry is None:
            return False

        record = self.registry.get(
            mission.mission_id
        )

        if record is None:
            return True

        return record.status in {
            ControlMissionStatus.FAILED,
            ControlMissionStatus.COMPLETED,
        }