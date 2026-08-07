"""
TODOBA Execution Mission API

Exposes the remote mission polling boundary.

This module owns HTTP transport only.
Mission storage, delivery leasing, serialization,
and authentication policy belong to separate capabilities.
"""

from typing import Optional

from fastapi import APIRouter
from fastapi import Depends

from backend.trading.execution.execution_mission_delivery_lease_service import (
    ExecutionMissionDeliveryLeaseService,
)
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
    lease_service: Optional[
        ExecutionMissionDeliveryLeaseService
    ] = None,
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

    if (
        lease_service is not None
        and not isinstance(
            lease_service,
            ExecutionMissionDeliveryLeaseService,
        )
    ):
        raise TypeError(
            "lease_service must be "
            "ExecutionMissionDeliveryLeaseService."
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

        lease = None

        if lease_service is not None:
            lease = lease_service.acquire(
                mission_id=mission.mission_id,
                agent_id=authenticated_agent_id,
            )

        payload = ExecutionMissionSerializer.serialize(
            mission
        )

        response = {
            "status": "available",
            "mission": payload,
            "agent_id": authenticated_agent_id,
            **payload,
        }

        if lease is not None:
            response["delivery_lease"] = {
                "mission_id": lease.mission_id,
                "agent_id": lease.agent_id,
                "leased_at": lease.leased_at,
                "expires_at": lease.expires_at,
            }

        return response

    return router