"""
TODOBA Execution Mission Execution Started API

Receives execution started evidence from Trusted Agents.

This API owns HTTP transport only.
Storage and authentication policy belong to separate
capabilities.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)
from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def create_execution_mission_execution_started_router(
    store: ExecutionMissionExecutionStartedStore,
    authenticator: TrustedAgentAuthenticator,
) -> APIRouter:
    if not isinstance(
        store,
        ExecutionMissionExecutionStartedStore,
    ):
        raise TypeError(
            "create_execution_mission_execution_started_router "
            "requires ExecutionMissionExecutionStartedStore."
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

        store.push(
            evidence
        )

        return {
            "status": "execution_started",
            "mission_id": evidence.mission_id,
            "store_size": store.size(),
        }

    return router