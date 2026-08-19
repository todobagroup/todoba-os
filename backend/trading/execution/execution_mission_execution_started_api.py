"""
TODOBA Execution Mission Execution Started API

Receives execution started evidence from Trusted Agents.

This API owns HTTP transport only.
Evidence intake and authentication policy belong
to separate capabilities.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.execution_mission_evidence_intake import (
    ExecutionMissionEvidenceIntake,
    ExecutionMissionEvidenceOwnershipError,
)
from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def create_execution_mission_execution_started_router(
    intake: ExecutionMissionEvidenceIntake,
    authenticator: TrustedAgentAuthenticator,
) -> APIRouter:
    if not isinstance(
        intake,
        ExecutionMissionEvidenceIntake,
    ):
        raise TypeError(
            "create_execution_mission_execution_started_router "
            "requires ExecutionMissionEvidenceIntake."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_execution_mission_execution_started_router "
            "requires TrustedAgentAuthenticator."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/missions/execution_started"
    )
    def execution_started(
        evidence: ExecutionMissionExecutionStarted,
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        if evidence.agent_id != authenticated_agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Execution started evidence "
                    "does not belong to authenticated Agent."
                ),
            )

        try:
            intake.receive(
                evidence
            )
        except ExecutionMissionEvidenceOwnershipError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

        return {
            "status": "execution_started",
            "mission_id": evidence.mission_id,
            "store_size": (
                intake.execution_started_store.size()
            ),
        }

    return router