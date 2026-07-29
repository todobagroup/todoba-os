"""
TODOBA Execution Mission Acknowledgement API

Receives acknowledgement evidence from Trusted Agents.

This API owns transport only.
Storage belongs to ExecutionMissionAcknowledgementStore.
"""


from fastapi import APIRouter

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)


def create_execution_mission_acknowledgement_router(
    store: ExecutionMissionAcknowledgementStore,
) -> APIRouter:

    if not isinstance(
        store,
        ExecutionMissionAcknowledgementStore,
    ):
        raise TypeError(
            "create_execution_mission_acknowledgement_router "
            "requires ExecutionMissionAcknowledgementStore."
        )

    router = APIRouter()

    @router.post(
        "/missions/acknowledge"
    )
    def acknowledge_mission(
        acknowledgement: ExecutionMissionAcknowledgement,
    ):

        store.push(
            acknowledgement
        )

        return {
            "status": "acknowledged",
            "mission_id": acknowledgement.mission_id,
            "store_size": store.size(),
        }

    return router