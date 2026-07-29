"""
TODOBA Execution Mission Failed Processor

Consumes Trusted Agent failure evidence
and coordinates mission lifecycle updates.

This component does not:
- receive HTTP requests
- store failure evidence
- execute broker orders
"""

from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
)

from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)


class ExecutionMissionFailedProcessor:
    """
    Processes execution failure evidence.
    """

    def __init__(
        self,
        *,
        store: ExecutionMissionFailedStore,
        lifecycle_service: ExecutionMissionLifecycleService,
    ) -> None:

        if not isinstance(
            store,
            ExecutionMissionFailedStore,
        ):
            raise TypeError(
                "ExecutionMissionFailedProcessor "
                "requires ExecutionMissionFailedStore."
            )

        if not isinstance(
            lifecycle_service,
            ExecutionMissionLifecycleService,
        ):
            raise TypeError(
                "ExecutionMissionFailedProcessor "
                "requires ExecutionMissionLifecycleService."
            )

        self.store = store
        self.lifecycle_service = lifecycle_service

    def process_next(self):

        evidence = self.store.pop()

        if evidence is None:
            return None

        return self.lifecycle_service.fail_execution(
            mission_id=evidence.mission_id,
            failed_at=evidence.failed_at,
            failure_reason=evidence.failure_reason,
        )
    