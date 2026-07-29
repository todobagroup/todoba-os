"""
TODOBA Execution Mission Execution Started Processor

Consumes execution started evidence and coordinates
mission lifecycle updates.

This component does not:
- receive HTTP requests
- store execution evidence
- execute broker orders
"""

from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)

from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)

from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)


class ExecutionMissionExecutionStartedProcessor:
    """
    Processes Trusted Agent execution started evidence.
    """

    def __init__(
        self,
        *,
        store: ExecutionMissionExecutionStartedStore,
        lifecycle_service: ExecutionMissionLifecycleService,
    ) -> None:

        if not isinstance(
            store,
            ExecutionMissionExecutionStartedStore,
        ):
            raise TypeError(
                "ExecutionMissionExecutionStartedProcessor "
                "requires ExecutionMissionExecutionStartedStore."
            )

        if not isinstance(
            lifecycle_service,
            ExecutionMissionLifecycleService,
        ):
            raise TypeError(
                "ExecutionMissionExecutionStartedProcessor "
                "requires ExecutionMissionLifecycleService."
            )

        self.store = store
        self.lifecycle_service = lifecycle_service

    def process_next(self):

        evidence = self.store.pop()

        if evidence is None:
            return None

        return self.lifecycle_service.start_execution(
            mission_id=evidence.mission_id,
            started_at=evidence.started_at,
        )