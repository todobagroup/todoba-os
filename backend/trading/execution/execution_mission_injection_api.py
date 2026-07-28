"""
TODOBA Execution Mission Injection API

Provides a proof-only boundary for injecting
ExecutionMission objects into the active mission store.

This component exists for Proof 001 validation only.
Production mission creation belongs to a separate
capability.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
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
    store: ExecutionMissionStore,
) -> APIRouter:
    if not isinstance(
        store,
        ExecutionMissionStore,
    ):
        raise TypeError(
            "create_execution_mission_injection_router "
            "requires ExecutionMissionStore."
        )

    router = APIRouter()

    @router.post(
        "/missions/inject"
    )
    def inject_mission(
        request: ExecutionMissionRequest,
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

        store.push(
            mission
        )

        return {
            "status": "queued",
            "mission_id": mission.mission_id,
            "queue_size": store.size(),
        }

    return router