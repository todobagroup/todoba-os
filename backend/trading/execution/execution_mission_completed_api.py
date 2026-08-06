"""
TODOBA Execution Mission Completed API

Receives completion evidence from Trusted Agents.

This API owns HTTP transport only.
Storage and authentication policy belong to separate
capabilities.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def create_execution_mission_completed_router(
    store: ExecutionMissionCompletedStore,
    authenticator: TrustedAgentAuthenticator,
) -> APIRouter:
    if not isinstance(
        store,
        ExecutionMissionCompletedStore,
    ):
        raise TypeError(
            "create_execution_mission_completed_router "
            "requires ExecutionMissionCompletedStore."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_execution_mission_completed_router "
            "requires TrustedAgentAuthenticator."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/missions/completed"
    )
    def completed_mission(
        evidence: ExecutionMissionCompleted,
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        if evidence.agent_id != authenticated_agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Completion evidence does not belong "
                    "to authenticated Agent."
                ),
            )

        store.push(
            evidence
        )

        return {
            "status": "completed",
            "mission_id": evidence.mission_id,
            "store_size": store.size(),
        }

    return router