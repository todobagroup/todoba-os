"""
TODOBA Execution Mission Status API

Exposes read-only execution mission lifecycle status.

This API owns HTTP transport and response mapping only.
Mission records belong to ExecutionMissionRegistry.
"""

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


def create_execution_mission_status_router(
    registry: ExecutionMissionRegistry,
) -> APIRouter:
    if not isinstance(
        registry,
        ExecutionMissionRegistry,
    ):
        raise TypeError(
            "create_execution_mission_status_router "
            "requires ExecutionMissionRegistry."
        )

    router = APIRouter()

    @router.get(
        "/missions/{mission_id}/status"
    )
    def mission_status(
        mission_id: str,
    ):
        record = registry.get(
            mission_id
        )

        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution mission record not found.",
            )

        return {
            "mission_id": record.mission.mission_id,
            "agent_id": record.mission.agent_id,
            "status": record.status.value,
            "delivered_at": record.delivered_at,
            "acknowledged_at": record.acknowledged_at,
            "started_at": record.started_at,
            "completed_at": record.completed_at,
            "failed_at": record.failed_at,
            "failure_reason": record.failure_reason,
        }

    return router