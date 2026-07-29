"""
TODOBA Execution Mission Acknowledgement Processor

Consumes acknowledgement evidence and coordinates
mission lifecycle updates.

This component does not:
- receive HTTP requests
- store acknowledgement evidence
- execute broker orders
"""

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)

from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)

from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)


class ExecutionMissionAcknowledgementProcessor:
    """
    Processes Trusted Agent acknowledgement evidence.
    """

    def __init__(
        self,
        *,
        store: ExecutionMissionAcknowledgementStore,
        lifecycle_service: ExecutionMissionLifecycleService,
    ) -> None:

        if not isinstance(
            store,
            ExecutionMissionAcknowledgementStore,
        ):
            raise TypeError(
                "ExecutionMissionAcknowledgementProcessor "
                "requires ExecutionMissionAcknowledgementStore."
            )

        if not isinstance(
            lifecycle_service,
            ExecutionMissionLifecycleService,
        ):
            raise TypeError(
                "ExecutionMissionAcknowledgementProcessor "
                "requires ExecutionMissionLifecycleService."
            )

        self.store = store
        self.lifecycle_service = lifecycle_service

    def process_next(self):

        acknowledgement = self.store.pop()

        if acknowledgement is None:
            return None

        return self.lifecycle_service.acknowledge(
            mission_id=acknowledgement.mission_id,
            acknowledged_at=(
                acknowledgement.acknowledged_at
            ),
        )