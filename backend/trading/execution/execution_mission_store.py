"""
TODOBA Execution Mission Store

Owns the in-memory queue of remote execution missions.

The store provides process-level mission idempotency and
explicit redelivery after a previous delivery attempt.
Persistence, security, signing, and broker execution
belong to separate capabilities.
"""

from collections import deque
from typing import Optional

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)


class ExecutionMissionStore:
    """
    Store pending execution missions for Trusted Agents.
    """

    def __init__(self) -> None:
        self._missions: deque[ExecutionMission] = deque()

        self._known_missions: dict[
            str,
            ExecutionMission,
        ] = {}

    @staticmethod
    def _require_mission(
        mission: ExecutionMission,
        *,
        operation: str,
    ) -> None:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                f"{operation} requires ExecutionMission."
            )

    def _existing_or_raise(
        self,
        mission: ExecutionMission,
    ) -> Optional[ExecutionMission]:
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
        mission: ExecutionMission,
    ) -> ExecutionMission:
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
        mission: ExecutionMission,
    ) -> ExecutionMission:
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
    ) -> Optional[ExecutionMission]:
        if not self._missions:
            return None

        return self._missions.popleft()

    def pop_for_agent(
        self,
        agent_id: str,
    ) -> Optional[ExecutionMission]:
        """
        Return the first queued mission belonging
        to the requested Trusted Agent.
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
    ) -> Optional[ExecutionMission]:
        return self._known_missions.get(
            mission_id
        )

    def size(
        self,
    ) -> int:
        return len(
            self._missions
        )