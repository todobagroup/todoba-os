"""
TODOBA Execution Mission Failed API

Receives failure evidence from Trusted Agents.

This API owns HTTP transport only.
Storage and authentication policy belong to separate
capabilities.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.execution_mission_failed import (
    ExecutionMissionFailed,
)
from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def create_execution_mission_failed_router(
    store: ExecutionMissionFailedStore,
    authenticator: TrustedAgentAuthenticator,
) -> APIRouter:
    if not isinstance(
        store,
        ExecutionMissionFailedStore,
    ):
        raise TypeError(
            "create_execution_mission_failed_router "
            "requires ExecutionMissionFailedStore."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_execution_mission_failed_router "
            "requires TrustedAgentAuthenticator."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/missions/failed"
    )
    def failed_mission(
        evidence: ExecutionMissionFailed,
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        if evidence.agent_id != authenticated_agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Failure evidence does not belong "
                    "to authenticated Agent."
                ),
            )

        store.push(
            evidence
        )

        return {
            "status": "failed",
            "mission_id": evidence.mission_id,
            "store_size": store.size(),
        }

    return router