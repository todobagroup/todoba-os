"""
TODOBA Execution Mission Acknowledgement API

Receives acknowledgement evidence from Trusted Agents.

This API owns HTTP transport only.
Storage and authentication policy belong to separate
capabilities.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def create_execution_mission_acknowledgement_router(
    store: ExecutionMissionAcknowledgementStore,
    authenticator: TrustedAgentAuthenticator,
) -> APIRouter:
    if not isinstance(
        store,
        ExecutionMissionAcknowledgementStore,
    ):
        raise TypeError(
            "create_execution_mission_acknowledgement_router "
            "requires ExecutionMissionAcknowledgementStore."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_execution_mission_acknowledgement_router "
            "requires TrustedAgentAuthenticator."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/missions/acknowledge"
    )
    def acknowledge_mission(
        acknowledgement: ExecutionMissionAcknowledgement,
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        if acknowledgement.agent_id != authenticated_agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Acknowledgement evidence does not belong "
                    "to authenticated Agent."
                ),
            )

        store.push(
            acknowledgement
        )

        return {
            "status": "acknowledged",
            "mission_id": acknowledgement.mission_id,
            "store_size": store.size(),
        }

    return router