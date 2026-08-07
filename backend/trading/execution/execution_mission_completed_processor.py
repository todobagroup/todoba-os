"""
TODOBA Execution Mission Completed Processor

Consumes Trusted Agent completion evidence
and coordinates mission lifecycle updates.

Responsibilities:
- process completion evidence
- remove successfully processed evidence
  from persistence

This component does not:
- receive HTTP requests
- store completion evidence
- execute broker orders
"""

from typing import Optional

from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)


class ExecutionMissionCompletedProcessor:
    """
    Processes execution completion evidence.
    """

    def __init__(
        self,
        *,
        store: ExecutionMissionCompletedStore,
        lifecycle_service: ExecutionMissionLifecycleService,
        persistence: Optional[
            ExecutionMissionEvidencePersistence
        ] = None,
    ) -> None:
        if not isinstance(
            store,
            ExecutionMissionCompletedStore,
        ):
            raise TypeError(
                "ExecutionMissionCompletedProcessor "
                "requires ExecutionMissionCompletedStore."
            )

        if not isinstance(
            lifecycle_service,
            ExecutionMissionLifecycleService,
        ):
            raise TypeError(
                "ExecutionMissionCompletedProcessor "
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

        result = self.lifecycle_service.complete_execution(
            mission_id=evidence.mission_id,
            completed_at=evidence.completed_at,
        )

        if self.persistence is not None:
            self.persistence.remove(
                evidence
            )

        return result