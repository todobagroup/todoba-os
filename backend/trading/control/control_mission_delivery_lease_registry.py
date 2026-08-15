"""
TODOBA Control Mission Delivery Lease Registry

Owns active control mission delivery leases.

Responsibilities:
- acquire delivery leases
- prevent conflicting Agent ownership
- return existing ownership for the same Agent
- expose active delivery leases
- release acknowledged or terminal delivery leases

This component does not:
- deliver control missions
- persist leases
- retry missions
- manage lease expiration
"""

from typing import Optional

from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
)


class ControlMissionDeliveryLeaseRegistry:
    """
    Registry for active control mission delivery leases.
    """

    def __init__(
        self,
    ) -> None:
        self._leases: dict[
            str,
            ControlMissionDeliveryLease,
        ] = {}

    def acquire(
        self,
        lease: ControlMissionDeliveryLease,
    ) -> ControlMissionDeliveryLease:
        if not isinstance(
            lease,
            ControlMissionDeliveryLease,
        ):
            raise TypeError(
                "acquire requires "
                "ControlMissionDeliveryLease."
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
            "Control mission delivery lease "
            "already belongs to another Agent."
        )

    def get(
        self,
        mission_id: str,
    ) -> Optional[
        ControlMissionDeliveryLease
    ]:
        return self._leases.get(
            mission_id
        )

    def list(
        self,
    ) -> list[
        ControlMissionDeliveryLease
    ]:
        return list(
            self._leases.values()
        )

    def release(
        self,
        mission_id: str,
    ) -> Optional[
        ControlMissionDeliveryLease
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