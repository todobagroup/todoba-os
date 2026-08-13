"""
TODOBA Execution Mission Injection API

Provides the authenticated HTTP boundary for injecting
ExecutionMission objects into TODOBA Cloud.

Business orchestration belongs to
ExecutionMissionService.

Executor authentication belongs to
ExecutorAuthenticator.
"""

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_service import (
    ExecutionMissionService,
)
from backend.trading.execution.executor_authentication_dependency import (
    create_executor_authentication_dependency,
)
from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)


class ExecutionMissionRequest(BaseModel):
    mission_id: str
    agent_id: str
    account_fingerprint: str

    symbol: str
    order_type: str

    volume: float
    entry: float | None

    sl: float
    tp: float

    magic_number: int
    comment: str

    created_at: str
    expires_at: str

    sequence: int


def create_execution_mission_injection_router(
    service: ExecutionMissionService,
    authenticator: ExecutorAuthenticator,
) -> APIRouter:
    if not isinstance(
        service,
        ExecutionMissionService,
    ):
        raise TypeError(
            "create_execution_mission_injection_router "
            "requires ExecutionMissionService."
        )

    if not isinstance(
        authenticator,
        ExecutorAuthenticator,
    ):
        raise TypeError(
            "create_execution_mission_injection_router "
            "requires ExecutorAuthenticator."
        )

    require_executor = (
        create_executor_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/missions/inject"
    )
    def inject_mission(
        request: ExecutionMissionRequest,
        executor_id: str = Depends(
            require_executor
        ),
    ):
        mission = ExecutionMission(
            mission_id=request.mission_id,
            agent_id=request.agent_id,
            account_fingerprint=(
                request.account_fingerprint
            ),
            symbol=request.symbol,
            order_type=request.order_type,
            volume=request.volume,
            entry=request.entry,
            sl=request.sl,
            tp=request.tp,
            magic_number=request.magic_number,
            comment=request.comment,
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