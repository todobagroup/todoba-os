"""
TODOBA Execution Mission Delivery Lease Registry

Owns active execution mission delivery leases.

Responsibilities:
- acquire delivery leases
- prevent conflicting agent ownership
- return existing ownership for the same agent
- expose active delivery leases
- release completed delivery leases

This component does not:
- deliver missions
- persist leases
- retry missions
- manage lease expiration
"""

from typing import Optional

from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)


class ExecutionMissionDeliveryLeaseRegistry:
    """
    Registry for active execution mission delivery leases.
    """

    def __init__(
        self,
    ) -> None:
        self._leases: dict[
            str,
            ExecutionMissionDeliveryLease,
        ] = {}

    def acquire(
        self,
        lease: ExecutionMissionDeliveryLease,
    ) -> ExecutionMissionDeliveryLease:
        if not isinstance(
            lease,
            ExecutionMissionDeliveryLease,
        ):
            raise TypeError(
                "acquire requires "
                "ExecutionMissionDeliveryLease."
            )

        existing = self._leases.get(
            lease.mission_id
        )

        if existing is None:
            self._leases[
                lease.mission_id
            ] = lease

            return lease

        if existing.agent_id == lease.agent_id:
            return existing

        raise ValueError(
            "Execution mission delivery lease "
            "already belongs to another Agent."
        )

    def get(
        self,
        mission_id: str,
    ) -> Optional[
        ExecutionMissionDeliveryLease
    ]:
        return self._leases.get(
            mission_id
        )

    def list(
        self,
    ) -> list[
        ExecutionMissionDeliveryLease
    ]:
        return list(
            self._leases.values()
        )

    def release(
        self,
        mission_id: str,
    ) -> Optional[
        ExecutionMissionDeliveryLease
    ]:
        return self._leases.pop(
            mission_id,
            None,
        )

    def size(
        self,
    ) -> int:
        return len(
            self._leases
        )