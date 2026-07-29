"""
TODOBA Execution Mission API

Exposes the remote mission polling boundary.

This module owns HTTP transport only.
Mission storage and serialization belong to separate
capabilities.
"""

from fastapi import APIRouter

from backend.trading.execution.execution_mission_serializer import (
    ExecutionMissionSerializer,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)


def create_execution_mission_router(
    store: ExecutionMissionStore,
) -> APIRouter:
    if not isinstance(
        store,
        ExecutionMissionStore,
    ):
        raise TypeError(
            "create_execution_mission_router requires "
            "ExecutionMissionStore."
        )

    router = APIRouter()

    @router.get(
        "/missions/next"
    )
    def next_mission():
        mission = store.pop()

        if mission is None:
            return {
                "status": "empty",
                "mission": None,
            }

        payload = (
            ExecutionMissionSerializer.serialize(
                mission
            )
        )

        return {
            "status": "available",
            "mission": payload,
            **payload,
        }

    return router