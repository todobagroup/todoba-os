"""
TODOBA Execution Mission Evidence Ownership

Authoritative ownership validation shared by execution
mission evidence intake and recovery.

Evidence is accepted only when:
- its mission exists in the authoritative mission registry
- its agent matches the authoritative mission owner
"""

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


class ExecutionMissionEvidenceOwnershipError(ValueError):
    """
    Raised when execution mission evidence cannot be
    proven to belong to its authoritative mission.
    """


def require_execution_mission_evidence_ownership(
    *,
    evidence: object,
    mission_registry: ExecutionMissionRegistry,
) -> None:
    if not isinstance(
        mission_registry,
        ExecutionMissionRegistry,
    ):
        raise TypeError(
            "mission_registry must be "
            "ExecutionMissionRegistry."
        )

    record = mission_registry.get(
        evidence.mission_id
    )

    if record is None:
        raise ExecutionMissionEvidenceOwnershipError(
            "Execution mission record not found."
        )

    if (
        record.mission.agent_id
        != evidence.agent_id
    ):
        raise ExecutionMissionEvidenceOwnershipError(
            "Execution mission evidence does not belong "
            "to mission Agent."
        )