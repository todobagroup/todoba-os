"""
TODOBA Execution Mission Execution Started API

Receives execution started evidence from Trusted Agents.

This API owns transport only.
Storage belongs to ExecutionMissionExecutionStartedStore.
"""


from fastapi import APIRouter

from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)

from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)


def create_execution_mission_execution_started_router(
    store: ExecutionMissionExecutionStartedStore,
) -> APIRouter:

    if not isinstance(
        store,
        ExecutionMissionExecutionStartedStore,
    ):
        raise TypeError(
            "create_execution_mission_execution_started_router "
            "requires ExecutionMissionExecutionStartedStore."
        )

    router = APIRouter()

    @router.post(
        "/missions/execution_started"
    )
    def execution_started(
        evidence: ExecutionMissionExecutionStarted,
    ):

        store.push(
            evidence
        )

        return {
            "status": "execution_started",
            "mission_id": evidence.mission_id,
            "store_size": store.size(),
        }

    return router