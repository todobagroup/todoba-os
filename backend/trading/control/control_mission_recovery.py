"""
TODOBA Control Mission Recovery

Restores eligible control missions after runtime restart.

Responsibilities:

- restore persisted control missions
- verify lifecycle record ownership
- remove orphaned missions
- remove terminal FAILED and COMPLETED missions
- preserve active delivery lease ownership
- recover CREATED missions through lifecycle service
- redeliver only eligible missions
- persist recovery cleanup

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
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
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

    _TERMINAL_STATUSES = {
        ControlMissionStatus.FAILED,
        ControlMissionStatus.COMPLETED,
    }

    _REDELIVERABLE_STATUSES = {
        ControlMissionStatus.QUEUED,
        ControlMissionStatus.DELIVERED,
    }

    def __init__(
        self,
        *,
        repository: ControlMissionRepository,
        persistence: ControlMissionPersistence,
        delivery_bridge: ControlMissionDeliveryBridge,
        registry: Optional[
            ControlMissionRegistry
        ] = None,
        lifecycle_service: Optional[
            ControlMissionLifecycleService
        ] = None,
        lease_registry: Optional[
            ControlMissionDeliveryLeaseRegistry
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

        if (
            lifecycle_service is not None
            and not isinstance(
                lifecycle_service,
                ControlMissionLifecycleService,
            )
        ):
            raise TypeError(
                "lifecycle_service must be "
                "ControlMissionLifecycleService."
            )

        if (
            lease_registry is not None
            and not isinstance(
                lease_registry,
                ControlMissionDeliveryLeaseRegistry,
            )
        ):
            raise TypeError(
                "lease_registry must be "
                "ControlMissionDeliveryLeaseRegistry."
            )

        if (
            lifecycle_service is not None
            and registry is None
        ):
            raise ValueError(
                "lifecycle_service requires registry."
            )

        self.repository = repository
        self.persistence = persistence
        self.delivery_bridge = delivery_bridge
        self.registry = registry
        self.lifecycle_service = lifecycle_service
        self.lease_registry = lease_registry

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
            record = self._get_record(
                mission
            )

            if self._must_remove(
                record
            ):
                removed = self.repository.remove(
                    mission.mission_id
                )

                if removed:
                    repository_changed = True

                continue

            if self._has_delivery_lease(
                mission.mission_id
            ):
                continue

            if not self._prepare_for_redelivery(
                mission=mission,
                record=record,
            ):
                continue

            self.delivery_bridge.redeliver(
                mission
            )

            restored_count += 1

        if repository_changed:
            self.persistence.save(
                self.repository
            )

        return restored_count

    def _get_record(
        self,
        mission: ControlMission,
    ):
        if self.registry is None:
            return None

        return self.registry.get(
            mission.mission_id
        )

    def _must_remove(
        self,
        record,
    ) -> bool:
        if self.registry is None:
            return False

        if record is None:
            return True

        return (
            record.status
            in self._TERMINAL_STATUSES
        )

    def _has_delivery_lease(
        self,
        mission_id: str,
    ) -> bool:
        if self.lease_registry is None:
            return False

        return (
            self.lease_registry.get(
                mission_id
            )
            is not None
        )

    def _prepare_for_redelivery(
        self,
        *,
        mission: ControlMission,
        record,
    ) -> bool:
        if self.registry is None:
            return True

        if record.status is ControlMissionStatus.CREATED:
            if self.lifecycle_service is None:
                return False

            record = self.lifecycle_service.queue(
                mission.mission_id
            )

        return (
            record.status
            in self._REDELIVERABLE_STATUSES
        )