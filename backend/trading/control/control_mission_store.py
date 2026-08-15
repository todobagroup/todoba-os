"""
TODOBA Control Mission Store

Owns the in-memory delivery queue of remote control
missions.

The store provides process-level mission idempotency and
explicit redelivery after a previous delivery attempt.
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

    @staticmethod
    def _require_mission(
        mission: ControlMission,
        *,
        operation: str,
    ) -> None:
        if not isinstance(
            mission,
            ControlMission,
        ):
            raise TypeError(
                f"{operation} requires ControlMission."
            )

    def _existing_or_raise(
        self,
        mission: ControlMission,
    ) -> Optional[ControlMission]:
        existing = self._known_missions.get(
            mission.mission_id
        )

        if (
            existing is not None
            and existing != mission
        ):
            raise ValueError(
                "mission_id already exists with "
                "different payload."
            )

        return existing

    def _is_queued(
        self,
        mission_id: str,
    ) -> bool:
        return any(
            queued.mission_id == mission_id
            for queued in self._missions
        )

    def push(
        self,
        mission: ControlMission,
    ) -> ControlMission:
        self._require_mission(
            mission,
            operation="push",
        )

        existing = self._existing_or_raise(
            mission
        )

        if existing is not None:
            return existing

        self._known_missions[
            mission.mission_id
        ] = mission

        self._missions.append(
            mission
        )

        return mission

    def redeliver(
        self,
        mission: ControlMission,
    ) -> ControlMission:
        """
        Requeue one known mission after a delivery attempt.

        A mission already waiting in the queue is not added
        again. An unknown mission is registered and queued.
        """

        self._require_mission(
            mission,
            operation="redeliver",
        )

        existing = self._existing_or_raise(
            mission
        )

        if existing is None:
            return self.push(
                mission
            )

        if self._is_queued(
            mission.mission_id
        ):
            return existing

        self._missions.append(
            existing
        )

        return existing

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