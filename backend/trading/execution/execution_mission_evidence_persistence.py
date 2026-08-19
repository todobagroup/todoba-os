"""
TODOBA Execution Mission Evidence Persistence

Persists unprocessed execution mission evidence to disk.

Responsibilities:
- append received evidence to persistent storage
- remove evidence after successful processing
- restore evidence into the correct in-memory store
- restore accepted evidence identities when configured

This component does not:
- process lifecycle transitions
- receive HTTP requests
- execute broker orders
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
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
    require_execution_mission_evidence_ownership,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
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


ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
EXECUTION_STARTED = "EXECUTION_STARTED"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
BROKER_EXECUTION = "BROKER_EXECUTION"


class ExecutionMissionEvidencePersistence:
    """
    Persistent queue for unprocessed execution evidence.
    """

    def __init__(
        self,
        storage_path: Path,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        self.storage_path = storage_path

    def save(
        self,
        evidence: object,
    ) -> None:
        """
        Append one unprocessed evidence object.
        """

        item = self._serialize(
            evidence
        )

        payload = self._read_payload()

        payload.append(
            item
        )

        self._write_payload(
            payload
        )

    def remove(
        self,
        evidence: object,
    ) -> bool:
        """
        Remove the first matching evidence item.

        Returns True when an item was removed.
        """

        expected = self._serialize(
            evidence
        )

        payload = self._read_payload()

        for index, item in enumerate(
            payload
        ):
            if item == expected:
                del payload[index]

                self._write_payload(
                    payload
                )

                return True

        return False

    def restore(
        self,
        *,
        acknowledgement_store: (
            ExecutionMissionAcknowledgementStore
        ),
        execution_started_store: (
            ExecutionMissionExecutionStartedStore
        ),
        completed_store: (
            ExecutionMissionCompletedStore
        ),
        failed_store: (
            ExecutionMissionFailedStore
        ),
        broker_evidence_store: (
            BrokerExecutionEvidenceStore
        ),
        mission_registry: ExecutionMissionRegistry,
        idempotency_registry: Optional[
            ExecutionMissionEvidenceIdempotencyRegistry
        ] = None,
    ) -> int:
        """
        Restore persisted evidence into its owner store.

        When an idempotency registry is configured,
        restored identities are registered and duplicate
        persisted evidence is not enqueued more than once.
        """

        self._validate_stores(
            acknowledgement_store=(
                acknowledgement_store
            ),
            execution_started_store=(
                execution_started_store
            ),
            completed_store=completed_store,
            failed_store=failed_store,
            broker_evidence_store=(
                broker_evidence_store
            ),
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

        payload = self._read_payload()

        restored = 0

        for item in payload:
            evidence_type = item.get(
                "evidence_type"
            )

            evidence_payload = item.get(
                "payload"
            )

            if not isinstance(
                evidence_payload,
                dict,
            ):
                raise ValueError(
                    "Evidence payload must be an object."
                )

            evidence = self._deserialize(
                evidence_type=evidence_type,
                evidence_payload=evidence_payload,
            )

            require_execution_mission_evidence_ownership(
                evidence=evidence,
                mission_registry=mission_registry,
            )

            if idempotency_registry is not None:
                identity = (
                    ExecutionMissionEvidenceIdentity.build(
                        evidence
                    )
                )

                accepted = idempotency_registry.accept(
                    identity
                )

                if not accepted:
                    continue

            self._push_restored_evidence(
                evidence=evidence,
                acknowledgement_store=(
                    acknowledgement_store
                ),
                execution_started_store=(
                    execution_started_store
                ),
                completed_store=completed_store,
                failed_store=failed_store,
                broker_evidence_store=(
                    broker_evidence_store
                ),
            )

            restored += 1

        return restored

    def size(
        self,
    ) -> int:
        return len(
            self._read_payload()
        )

    def _serialize(
        self,
        evidence: object,
    ) -> dict[str, Any]:
        if isinstance(
            evidence,
            ExecutionMissionAcknowledgement,
        ):
            evidence_type = ACKNOWLEDGEMENT

        elif isinstance(
            evidence,
            ExecutionMissionExecutionStarted,
        ):
            evidence_type = EXECUTION_STARTED

        elif isinstance(
            evidence,
            ExecutionMissionCompleted,
        ):
            evidence_type = COMPLETED

        elif isinstance(
            evidence,
            ExecutionMissionFailed,
        ):
            evidence_type = FAILED

        elif isinstance(
            evidence,
            BrokerExecutionEvidence,
        ):
            evidence_type = BROKER_EXECUTION

        else:
            raise TypeError(
                "Unsupported execution mission evidence."
            )

        return {
            "evidence_type": evidence_type,
            "payload": asdict(
                evidence
            ),
        }

    def _deserialize(
        self,
        *,
        evidence_type: object,
        evidence_payload: dict[str, Any],
    ) -> object:
        if evidence_type == ACKNOWLEDGEMENT:
            return ExecutionMissionAcknowledgement(
                **evidence_payload
            )

        if evidence_type == EXECUTION_STARTED:
            return ExecutionMissionExecutionStarted(
                **evidence_payload
            )

        if evidence_type == COMPLETED:
            return ExecutionMissionCompleted(
                **evidence_payload
            )

        if evidence_type == FAILED:
            return ExecutionMissionFailed(
                **evidence_payload
            )

        if evidence_type == BROKER_EXECUTION:
            return BrokerExecutionEvidence(
                **evidence_payload
            )

        raise ValueError(
            "Unsupported execution mission "
            "evidence type."
        )

    def _push_restored_evidence(
        self,
        *,
        evidence: object,
        acknowledgement_store: (
            ExecutionMissionAcknowledgementStore
        ),
        execution_started_store: (
            ExecutionMissionExecutionStartedStore
        ),
        completed_store: (
            ExecutionMissionCompletedStore
        ),
        failed_store: (
            ExecutionMissionFailedStore
        ),
        broker_evidence_store: (
            BrokerExecutionEvidenceStore
        ),
    ) -> None:
        if isinstance(
            evidence,
            ExecutionMissionAcknowledgement,
        ):
            acknowledgement_store.push(
                evidence
            )
            return

        if isinstance(
            evidence,
            ExecutionMissionExecutionStarted,
        ):
            execution_started_store.push(
                evidence
            )
            return

        if isinstance(
            evidence,
            ExecutionMissionCompleted,
        ):
            completed_store.push(
                evidence
            )
            return

        if isinstance(
            evidence,
            ExecutionMissionFailed,
        ):
            failed_store.push(
                evidence
            )
            return

        if isinstance(
            evidence,
            BrokerExecutionEvidence,
        ):
            broker_evidence_store.push(
                evidence
            )
            return

        raise TypeError(
            "Unsupported execution mission evidence."
        )

    def _read_payload(
        self,
    ) -> list[dict[str, Any]]:
        if not self.storage_path.exists():
            return []

        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8",
            )
        )

        if not isinstance(
            payload,
            list,
        ):
            raise ValueError(
                "Evidence persistence payload "
                "must be a list."
            )

        return payload

    def _write_payload(
        self,
        payload: list[dict[str, Any]],
    ) -> None:
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.storage_path.write_text(
            json.dumps(
                payload,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _validate_stores(
        self,
        *,
        acknowledgement_store: (
            ExecutionMissionAcknowledgementStore
        ),
        execution_started_store: (
            ExecutionMissionExecutionStartedStore
        ),
        completed_store: (
            ExecutionMissionCompletedStore
        ),
        failed_store: (
            ExecutionMissionFailedStore
        ),
        broker_evidence_store: (
            BrokerExecutionEvidenceStore
        ),
    ) -> None:
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