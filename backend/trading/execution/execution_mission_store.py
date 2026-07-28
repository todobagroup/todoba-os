"""
TODOBA Execution Mission Store

Owns the in-memory queue of remote execution missions.

This component belongs to the transport boundary.
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

    def push(
        self,
        mission: ExecutionMission,
    ) -> ExecutionMission:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "push requires ExecutionMission."
            )

        self._missions.append(
            mission
        )

        return mission

    def pop(self) -> Optional[ExecutionMission]:
        if not self._missions:
            return None

        return self._missions.popleft()

    def size(self) -> int:
        return len(
            self._missions
        )