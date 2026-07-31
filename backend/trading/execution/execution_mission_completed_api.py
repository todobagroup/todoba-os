"""
TODOBA Execution Mission Completed API

Receives completion evidence from Trusted Agents.

This API owns transport only.
Storage belongs to ExecutionMissionCompletedStore.
"""


from fastapi import APIRouter

from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)

from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)


def create_execution_mission_completed_router(
    store: ExecutionMissionCompletedStore,
) -> APIRouter:

    if not isinstance(
        store,
        ExecutionMissionCompletedStore,
    ):
        raise TypeError(
            "create_execution_mission_completed_router "
            "requires ExecutionMissionCompletedStore."
        )

    router = APIRouter()

    @router.post(
        "/missions/completed"
    )
    def completed_mission(
        evidence: ExecutionMissionCompleted,
    ):

        store.push(
            evidence
        )

        return {
            "status": "completed",
            "mission_id": evidence.mission_id,
            "store_size": store.size(),
        }

    return router