"""
TODOBA Control Mission Injection API

Provides the authenticated HTTP boundary for injecting
ControlMission objects into TODOBA Cloud.

Business orchestration belongs to ControlMissionService.
Executor authentication belongs to ExecutorAuthenticator.
"""

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_service import (
    ControlMissionService,
)
from backend.trading.execution.executor_authentication_dependency import (
    create_executor_authentication_dependency,
)
from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)


class ControlMissionRequest(BaseModel):
    mission_id: str
    agent_id: str
    account_fingerprint: str

    action: ControlAction
    symbol: str
    magic_number: int

    requested_by_sender_id: int

    created_at: str
    expires_at: str
    sequence: int


def create_control_mission_injection_router(
    service: ControlMissionService,
    authenticator: ExecutorAuthenticator,
) -> APIRouter:
    if not isinstance(
        service,
        ControlMissionService,
    ):
        raise TypeError(
            "create_control_mission_injection_router "
            "requires ControlMissionService."
        )

    if not isinstance(
        authenticator,
        ExecutorAuthenticator,
    ):
        raise TypeError(
            "create_control_mission_injection_router "
            "requires ExecutorAuthenticator."
        )

    require_executor = (
        create_executor_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/control/missions/inject"
    )
    def inject_control_mission(
        request: ControlMissionRequest,
        executor_id: str = Depends(
            require_executor
        ),
    ):
        mission = ControlMission(
            mission_id=request.mission_id,
            agent_id=request.agent_id,
            account_fingerprint=(
                request.account_fingerprint
            ),
            action=request.action,
            symbol=request.symbol,
            magic_number=request.magic_number,
            requested_by_sender_id=(
                request.requested_by_sender_id
            ),
            created_at=request.created_at,
            expires_at=request.expires_at,
            sequence=request.sequence,
        )

        service.create_mission(
            mission
        )

        return {
            "status": "persisted",
            "mission_id": mission.mission_id,
        }

    return router