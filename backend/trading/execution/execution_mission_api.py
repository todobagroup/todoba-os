"""
TODOBA Execution Mission API

Exposes the remote mission polling boundary.

This module owns HTTP transport only.
Mission storage, serialization, and authentication policy
belong to separate capabilities.
"""

from fastapi import APIRouter
from fastapi import Depends

from backend.trading.execution.execution_mission_serializer import (
    ExecutionMissionSerializer,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def create_execution_mission_router(
    store: ExecutionMissionStore,
    authenticator: TrustedAgentAuthenticator,
) -> APIRouter:
    if not isinstance(
        store,
        ExecutionMissionStore,
    ):
        raise TypeError(
            "create_execution_mission_router requires "
            "ExecutionMissionStore."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_execution_mission_router requires "
            "TrustedAgentAuthenticator."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.get(
        "/missions/next",
    )
    def next_mission(
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        mission = store.pop_for_agent(
            authenticated_agent_id
        )

        if mission is None:
            return {
                "status": "empty",
                "mission": None,
            }

        payload = ExecutionMissionSerializer.serialize(
            mission
        )

        return {
            "status": "available",
            "mission": payload,
            "agent_id": authenticated_agent_id,
            **payload,
        }

    return router