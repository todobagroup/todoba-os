"""
TODOBA Execution Mission Evidence Identity

Creates stable identities for execution mission evidence.

Responsibilities:
- identify lifecycle evidence by type and mission
- identify broker evidence by mission and trade tickets

This component does not:
- persist identities
- decide duplicate handling
- receive HTTP requests
- modify mission lifecycle
"""

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)
from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)
from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)
from backend.trading.execution.execution_mission_failed import (
    ExecutionMissionFailed,
)


ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
EXECUTION_STARTED = "EXECUTION_STARTED"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
BROKER_EXECUTION = "BROKER_EXECUTION"


class ExecutionMissionEvidenceIdentity:
    """
    Builds a stable identity for supported evidence.
    """

    @staticmethod
    def build(
        evidence: object,
    ) -> str:
        if isinstance(
            evidence,
            ExecutionMissionAcknowledgement,
        ):
            return (
                f"{ACKNOWLEDGEMENT}:"
                f"{evidence.mission_id}"
            )

        if isinstance(
            evidence,
            ExecutionMissionExecutionStarted,
        ):
            return (
                f"{EXECUTION_STARTED}:"
                f"{evidence.mission_id}"
            )

        if isinstance(
            evidence,
            ExecutionMissionCompleted,
        ):
            return (
                f"{COMPLETED}:"
                f"{evidence.mission_id}"
            )

        if isinstance(
            evidence,
            ExecutionMissionFailed,
        ):
            return (
                f"{FAILED}:"
                f"{evidence.mission_id}"
            )

        if isinstance(
            evidence,
            BrokerExecutionEvidence,
        ):
            return (
                f"{BROKER_EXECUTION}:"
                f"{evidence.mission_id}:"
                f"{evidence.order_ticket}:"
                f"{evidence.deal_ticket}"
            )

        raise TypeError(
            "Unsupported execution mission evidence."
        )