"""
TODOBA Execution Mission Execution Started Processor

Consumes execution started evidence and coordinates
mission lifecycle updates.

Responsibilities:
- process execution started evidence
- remove successfully processed evidence
  from persistence

This component does not:
- receive HTTP requests
- store execution evidence
- execute broker orders
"""

from typing import Optional

from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
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
        persistence: Optional[
            ExecutionMissionEvidencePersistence
        ] = None,
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

        if (
            persistence is not None
            and not isinstance(
                persistence,
                ExecutionMissionEvidencePersistence,
            )
        ):
            raise TypeError(
                "persistence must be "
                "ExecutionMissionEvidencePersistence."
            )

        self.store = store
        self.lifecycle_service = lifecycle_service
        self.persistence = persistence

    def process_next(
        self,
    ):
        evidence = self.store.pop()

        if evidence is None:
            return None

        result = self.lifecycle_service.start_execution(
            mission_id=evidence.mission_id,
            started_at=evidence.started_at,
        )

        if self.persistence is not None:
            self.persistence.remove(
                evidence
            )

        return result