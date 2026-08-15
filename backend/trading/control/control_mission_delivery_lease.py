"""
TODOBA Control Mission Delivery Lease

Represents temporary in-flight delivery ownership
for one control mission.

A lease exists after a Trusted Agent polls a mission
and before TODOBA receives acknowledgement.

This component does not:
- deliver control missions
- persist control missions
- acknowledge control missions
- retry delivery
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ControlMissionDeliveryLease:
    """
    Immutable in-flight control mission delivery lease.
    """

    mission_id: str
    agent_id: str
    leased_at: str
    expires_at: str