"""
TODOBA Execution Mission Failed API

Receives failure evidence from Trusted Agents.

This API owns transport only.
Storage belongs to ExecutionMissionFailedStore.
"""


from fastapi import APIRouter

from backend.trading.execution.execution_mission_failed import (
    ExecutionMissionFailed,
)

from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
)


def create_execution_mission_failed_router(
    store: ExecutionMissionFailedStore,
) -> APIRouter:

    if not isinstance(
        store,
        ExecutionMissionFailedStore,
    ):
        raise TypeError(
            "create_execution_mission_failed_router "
            "requires ExecutionMissionFailedStore."
        )

    router = APIRouter()

    @router.post(
        "/missions/failed"
    )
    def failed_mission(
        evidence: ExecutionMissionFailed,
    ):

        store.push(
            evidence
        )

        return {
            "status": "failed",
            "mission_id": evidence.mission_id,
            "store_size": store.size(),
        }

    return router