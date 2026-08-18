"""
TODOBA Execution Mission Delivery Bridge

Moves execution missions into the delivery queue
consumed by Trusted Agents and supports explicit
redelivery after an incomplete delivery attempt.

This component does not:
- create missions
- persist missions
- execute broker orders
"""

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


class ExecutionMissionDeliveryBridge:
    """
    Bridge between mission ownership
    and Trusted Agent delivery queue.
    """

    def __init__(
        self,
        store: ExecutionMissionStore,
    ) -> None:
        if not isinstance(
            store,
            ExecutionMissionStore,
        ):
            raise TypeError(
                "ExecutionMissionDeliveryBridge "
                "requires ExecutionMissionStore."
            )

        self.store = store

    def deliver(
        self,
        mission: ExecutionMission,
    ) -> ExecutionMission:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "deliver requires ExecutionMission."
            )

        return self.store.push(
            mission
        )

    def redeliver(
        self,
        mission: ExecutionMission,
    ) -> ExecutionMission:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "redeliver requires ExecutionMission."
            )

        return self.store.redeliver(
            mission
        )