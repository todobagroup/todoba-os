"""
TODOBA Broker Execution Evidence Processor

Consumes broker execution evidence
and coordinates mission lifecycle updates.

Responsibilities:
- process broker execution evidence
- remove successfully processed evidence
  from persistence

This component does not:
- receive HTTP requests
- execute broker orders
- store evidence
"""

from typing import Optional

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)


class BrokerExecutionEvidenceProcessor:
    """
    Processes broker execution evidence.
    """

    def __init__(
        self,
        *,
        store: BrokerExecutionEvidenceStore,
        lifecycle_service: ExecutionMissionLifecycleService,
        persistence: Optional[
            ExecutionMissionEvidencePersistence
        ] = None,
    ) -> None:
        if not isinstance(
            store,
            BrokerExecutionEvidenceStore,
        ):
            raise TypeError(
                "BrokerExecutionEvidenceProcessor "
                "requires BrokerExecutionEvidenceStore."
            )

        if not isinstance(
            lifecycle_service,
            ExecutionMissionLifecycleService,
        ):
            raise TypeError(
                "BrokerExecutionEvidenceProcessor "
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

        if evidence.success:
            result = (
                self.lifecycle_service.complete_execution(
                    mission_id=evidence.mission_id,
                    completed_at=evidence.completed_at,
                )
            )
        else:
            result = (
                self.lifecycle_service.fail_execution(
                    mission_id=evidence.mission_id,
                    failed_at=evidence.completed_at,
                    failure_reason=evidence.comment,
                )
            )

        if self.persistence is not None:
            self.persistence.remove(
                evidence
            )

        return result