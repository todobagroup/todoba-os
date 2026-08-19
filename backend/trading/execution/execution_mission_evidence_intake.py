"""
TODOBA Execution Mission Evidence Intake

Safely accepts execution mission evidence.

Responsibilities:
- validate evidence ownership against the authoritative mission
- persist evidence before acknowledging receipt
- protect evidence intake from duplicate delivery
- push persisted evidence into the correct in-memory store

This component does not:
- receive HTTP requests
- process lifecycle transitions
- remove processed evidence
"""

from typing import Optional

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
from backend.trading.execution.execution_mission_evidence_idempotency_registry import (
    ExecutionMissionEvidenceIdempotencyRegistry,
)
from backend.trading.execution.execution_mission_evidence_identity import (
    ExecutionMissionEvidenceIdentity,
)
from backend.trading.execution.execution_mission_evidence_ownership import (
    ExecutionMissionEvidenceOwnershipError,
    require_execution_mission_evidence_ownership,
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
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


class ExecutionMissionEvidenceIntake:
    """
    Validates mission ownership, persists evidence,
    then places accepted evidence in memory.

    When an idempotency registry is configured,
    duplicate evidence is ignored safely.
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
        mission_registry: ExecutionMissionRegistry,
        idempotency_registry: Optional[
            ExecutionMissionEvidenceIdempotencyRegistry
        ] = None,
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

        if not isinstance(
            mission_registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "mission_registry must be "
                "ExecutionMissionRegistry."
            )

        if (
            idempotency_registry is not None
            and not isinstance(
                idempotency_registry,
                ExecutionMissionEvidenceIdempotencyRegistry,
            )
        ):
            raise TypeError(
                "idempotency_registry must be "
                "ExecutionMissionEvidenceIdempotencyRegistry."
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

        self.mission_registry = mission_registry

        self.idempotency_registry = (
            idempotency_registry
        )

    def receive(
        self,
        evidence: object,
    ) -> object | None:
        """
        Validate ownership, persist new evidence,
        then enqueue it in RAM.

        Returns the evidence when accepted.
        Returns None when the evidence is a duplicate.
        """

        store = self._resolve_store(
            evidence
        )

        require_execution_mission_evidence_ownership(
            evidence=evidence,
            mission_registry=self.mission_registry,
        )

        if self.idempotency_registry is None:
            self.persistence.save(
                evidence
            )

            store.push(
                evidence
            )

            return evidence

        identity = ExecutionMissionEvidenceIdentity.build(
            evidence
        )

        if self.idempotency_registry.contains(
            identity
        ):
            return None

        self.persistence.save(
            evidence
        )

        accepted = self.idempotency_registry.accept(
            identity
        )

        if not accepted:
            return None

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