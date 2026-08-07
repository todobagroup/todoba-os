"""
TODOBA Execution Mission Evidence Intake

Safely accepts execution mission evidence.

Responsibilities:
- persist evidence before acknowledging receipt
- push persisted evidence into the correct in-memory store

This component does not:
- receive HTTP requests
- process lifecycle transitions
- remove processed evidence
- decide evidence idempotency
"""

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)
from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)
from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)
from backend.trading.execution.execution_mission_failed import (
    ExecutionMissionFailed,
)
from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
)


class ExecutionMissionEvidenceIntake:
    """
    Persists evidence before placing it in memory.
    """

    def __init__(
        self,
        *,
        persistence: ExecutionMissionEvidencePersistence,
        acknowledgement_store: (
            ExecutionMissionAcknowledgementStore
        ),
        execution_started_store: (
            ExecutionMissionExecutionStartedStore
        ),
        completed_store: ExecutionMissionCompletedStore,
        failed_store: ExecutionMissionFailedStore,
        broker_evidence_store: BrokerExecutionEvidenceStore,
    ) -> None:
        if not isinstance(
            persistence,
            ExecutionMissionEvidencePersistence,
        ):
            raise TypeError(
                "ExecutionMissionEvidenceIntake requires "
                "ExecutionMissionEvidencePersistence."
            )

        if not isinstance(
            acknowledgement_store,
            ExecutionMissionAcknowledgementStore,
        ):
            raise TypeError(
                "acknowledgement_store must be "
                "ExecutionMissionAcknowledgementStore."
            )

        if not isinstance(
            execution_started_store,
            ExecutionMissionExecutionStartedStore,
        ):
            raise TypeError(
                "execution_started_store must be "
                "ExecutionMissionExecutionStartedStore."
            )

        if not isinstance(
            completed_store,
            ExecutionMissionCompletedStore,
        ):
            raise TypeError(
                "completed_store must be "
                "ExecutionMissionCompletedStore."
            )

        if not isinstance(
            failed_store,
            ExecutionMissionFailedStore,
        ):
            raise TypeError(
                "failed_store must be "
                "ExecutionMissionFailedStore."
            )

        if not isinstance(
            broker_evidence_store,
            BrokerExecutionEvidenceStore,
        ):
            raise TypeError(
                "broker_evidence_store must be "
                "BrokerExecutionEvidenceStore."
            )

        self.persistence = persistence
        self.acknowledgement_store = (
            acknowledgement_store
        )
        self.execution_started_store = (
            execution_started_store
        )
        self.completed_store = completed_store
        self.failed_store = failed_store
        self.broker_evidence_store = (
            broker_evidence_store
        )

    def receive(
        self,
        evidence: object,
    ) -> object:
        """
        Persist evidence first, then enqueue it in RAM.
        """

        store = self._resolve_store(
            evidence
        )

        self.persistence.save(
            evidence
        )

        store.push(
            evidence
        )

        return evidence

    def _resolve_store(
        self,
        evidence: object,
    ):
        if isinstance(
            evidence,
            ExecutionMissionAcknowledgement,
        ):
            return self.acknowledgement_store

        if isinstance(
            evidence,
            ExecutionMissionExecutionStarted,
        ):
            return self.execution_started_store

        if isinstance(
            evidence,
            ExecutionMissionCompleted,
        ):
            return self.completed_store

        if isinstance(
            evidence,
            ExecutionMissionFailed,
        ):
            return self.failed_store

        if isinstance(
            evidence,
            BrokerExecutionEvidence,
        ):
            return self.broker_evidence_store

        raise TypeError(
            "Unsupported execution mission evidence."
        )