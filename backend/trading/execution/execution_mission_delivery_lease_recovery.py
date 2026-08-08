"""
TODOBA Execution Mission Delivery Lease Recovery

Restores persisted execution mission delivery leases
into the active delivery lease registry.

Responsibilities:
- restore persisted delivery leases
- repopulate the active delivery lease registry
- report restored lease count

This component does not:
- create leases
- deliver missions
- acknowledge missions
- retry missions
- own persistence
"""

from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)


class ExecutionMissionDeliveryLeaseRecovery:
    """
    Restores execution mission delivery leases
    after runtime restart.
    """

    def __init__(
        self,
        *,
        persistence: ExecutionMissionDeliveryLeasePersistence,
        registry: ExecutionMissionDeliveryLeaseRegistry,
    ) -> None:
        if not isinstance(
            persistence,
            ExecutionMissionDeliveryLeasePersistence,
        ):
            raise TypeError(
                "ExecutionMissionDeliveryLeaseRecovery "
                "requires "
                "ExecutionMissionDeliveryLeasePersistence."
            )

        if not isinstance(
            registry,
            ExecutionMissionDeliveryLeaseRegistry,
        ):
            raise TypeError(
                "ExecutionMissionDeliveryLeaseRecovery "
                "requires "
                "ExecutionMissionDeliveryLeaseRegistry."
            )

        self.persistence = persistence
        self.registry = registry

    def restore(
        self,
    ) -> int:
        return self.persistence.restore(
            self.registry
        )