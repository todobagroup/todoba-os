"""
TODOBA Control Mission Store

Owns the in-memory delivery queue of remote control
missions.

The store provides process-level mission idempotency.
Persistence, signing, lifecycle tracking, HTTP transport,
and broker control belong to separate capabilities.
"""

from collections import deque
from typing import Optional

from backend.trading.control.control_mission import (
    ControlMission,
)


class ControlMissionStore:
    """
    Store pending control missions for Trusted Agents.
    """

    def __init__(self) -> None:
        self._missions: deque[ControlMission] = deque()
        self._known_missions: dict[
            str,
            ControlMission,
        ] = {}

    def push(
        self,
        mission: ControlMission,
    ) -> ControlMission:
        if not isinstance(
            mission,
            ControlMission,
        ):
            raise TypeError(
                "push requires ControlMission."
            )

        existing = self._known_missions.get(
            mission.mission_id
        )

        if existing is not None:
            if existing != mission:
                raise ValueError(
                    "mission_id already exists with "
                    "different payload."
                )

            return existing

        self._known_missions[
            mission.mission_id
        ] = mission

        self._missions.append(
            mission
        )

        return mission

    def pop(
        self,
    ) -> Optional[ControlMission]:
        if not self._missions:
            return None

        return self._missions.popleft()

    def pop_for_agent(
        self,
        agent_id: str,
    ) -> Optional[ControlMission]:
        """
        Return the first queued mission belonging to the
        requested Trusted Agent.
        """

        for mission in self._missions:
            if mission.agent_id == agent_id:
                self._missions.remove(
                    mission
                )

                return mission

        return None

    def get(
        self,
        mission_id: str,
    ) -> Optional[ControlMission]:
        return self._known_missions.get(
            mission_id
        )

    def size(self) -> int:
        return len(
            self._missions
        )