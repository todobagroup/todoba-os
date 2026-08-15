"""
TODOBA Control Mission Delivery Lease Recovery

Restores persisted control mission delivery leases
into the active delivery lease registry.

Responsibilities:
- restore persisted delivery leases
- repopulate the active delivery lease registry
- report restored lease count

This component does not:
- create leases
- deliver control missions
- acknowledge control missions
- retry missions
- own persistence
"""

from backend.trading.control.control_mission_delivery_lease_persistence import (
    ControlMissionDeliveryLeasePersistence,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)


class ControlMissionDeliveryLeaseRecovery:
    """
    Restores control mission delivery leases
    after runtime restart.
    """

    def __init__(
        self,
        *,
        persistence: ControlMissionDeliveryLeasePersistence,
        registry: ControlMissionDeliveryLeaseRegistry,
    ) -> None:
        if not isinstance(
            persistence,
            ControlMissionDeliveryLeasePersistence,
        ):
            raise TypeError(
                "ControlMissionDeliveryLeaseRecovery "
                "requires "
                "ControlMissionDeliveryLeasePersistence."
            )

        if not isinstance(
            registry,
            ControlMissionDeliveryLeaseRegistry,
        ):
            raise TypeError(
                "ControlMissionDeliveryLeaseRecovery "
                "requires "
                "ControlMissionDeliveryLeaseRegistry."
            )

        self.persistence = persistence
        self.registry = registry

    def restore(
        self,
    ) -> int:
        return self.persistence.restore(
            self.registry
        )