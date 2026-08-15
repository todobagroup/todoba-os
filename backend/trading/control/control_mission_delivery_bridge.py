"""
TODOBA Control Mission Delivery Bridge

Moves control missions into the delivery queue
consumed by Trusted Agents.

This component does not:
- create control missions
- persist control missions
- execute broker control actions
"""

from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)


class ControlMissionDeliveryBridge:
    """
    Bridge between control mission ownership
    and Trusted Agent delivery queue.
    """

    def __init__(
        self,
        store: ControlMissionStore,
    ) -> None:
        if not isinstance(
            store,
            ControlMissionStore,
        ):
            raise TypeError(
                "ControlMissionDeliveryBridge "
                "requires ControlMissionStore."
            )

        self.store = store

    def deliver(
        self,
        mission: ControlMission,
    ) -> ControlMission:
        if not isinstance(
            mission,
            ControlMission,
        ):
            raise TypeError(
                "deliver requires ControlMission."
            )

        return self.store.push(
            mission
        )