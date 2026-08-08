"""
TODOBA Execution Mission Repository

Owns organizational storage of execution missions.

This component:

- stores mission records
- provides mission lookup
- removes mission records
- supports persistence layer

It does not:

- write files
- execute broker orders
- manage MT5
"""

from typing import Optional

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)


class ExecutionMissionRepository:
    """
    Repository for execution missions.
    """

    def __init__(self) -> None:
        self._missions: dict[
            str,
            ExecutionMission,
        ] = {}

    def save(
        self,
        mission: ExecutionMission,
    ) -> ExecutionMission:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "save requires ExecutionMission."
            )

        self._missions[
            mission.mission_id
        ] = mission

        return mission

    def get(
        self,
        mission_id: str,
    ) -> Optional[ExecutionMission]:
        return self._missions.get(
            mission_id
        )

    def remove(
        self,
        mission_id: str,
    ) -> bool:
        if mission_id not in self._missions:
            return False

        del self._missions[
            mission_id
        ]

        return True

    def all(
        self,
    ) -> list[ExecutionMission]:
        return list(
            self._missions.values()
        )

    def size(
        self,
    ) -> int:
        return len(
            self._missions
        )