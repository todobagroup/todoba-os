"""
TODOBA Control Mission Repository

Owns organizational storage of control missions.

This component stores and retrieves immutable control
mission contracts. File persistence, delivery, lifecycle
tracking, and broker control belong elsewhere.
"""

from typing import Optional

from backend.trading.control.control_mission import (
    ControlMission,
)


class ControlMissionRepository:
    """
    Repository for control missions.
    """

    def __init__(self) -> None:
        self._missions: dict[
            str,
            ControlMission,
        ] = {}

    def save(
        self,
        mission: ControlMission,
    ) -> ControlMission:
        if not isinstance(
            mission,
            ControlMission,
        ):
            raise TypeError(
                "save requires ControlMission."
            )

        existing = self._missions.get(
            mission.mission_id
        )

        if existing is not None:
            if existing != mission:
                raise ValueError(
                    "mission_id already exists with "
                    "different payload."
                )

            return existing

        self._missions[
            mission.mission_id
        ] = mission

        return mission

    def get(
        self,
        mission_id: str,
    ) -> Optional[ControlMission]:
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

    def all(self) -> list[ControlMission]:
        return list(
            self._missions.values()
        )

    def size(self) -> int:
        return len(
            self._missions
        )