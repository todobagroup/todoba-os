"""
TODOBA Execution Mission Delivery Lease

Represents temporary in-flight delivery ownership
for one execution mission.

A lease exists after a Trusted Agent polls a mission
and before TODOBA receives acknowledgement.

This component does not:
- deliver missions
- persist missions
- acknowledge missions
- retry delivery
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionMissionDeliveryLease:
    """
    Immutable in-flight delivery lease.
    """

    mission_id: str

    agent_id: str

    leased_at: str

    expires_at: str