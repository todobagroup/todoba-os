"""
TODOBA Execution Mission Failed Processor

Consumes Trusted Agent failure evidence
and coordinates mission lifecycle updates.

Responsibilities:
- process failure evidence
- remove successfully processed evidence
  from persistence

This component does not:
- receive HTTP requests
- store failure evidence
- execute broker orders
"""

from typing import Optional

from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
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
        persistence: Optional[
            ExecutionMissionEvidencePersistence
        ] = None,
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

        result = self.lifecycle_service.fail_execution(
            mission_id=evidence.mission_id,
            failed_at=evidence.failed_at,
            failure_reason=evidence.failure_reason,
        )

        if self.persistence is not None:
            self.persistence.remove(
                evidence
            )

        return result