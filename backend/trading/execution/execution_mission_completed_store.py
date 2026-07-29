"""
TODOBA Execution Mission Completed Store

Stores Trusted Agent completion evidence.

This component owns completion evidence only.

It does not:
- process lifecycle transitions
- execute broker orders
- manage MT5
"""

from collections import deque
from typing import Optional

from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)


class ExecutionMissionCompletedStore:
    """
    In-memory store for execution completion evidence.
    """

    def __init__(self) -> None:
        self._evidence: deque[
            ExecutionMissionCompleted
        ] = deque()

    def push(
        self,
        evidence: ExecutionMissionCompleted,
    ) -> ExecutionMissionCompleted:

        if not isinstance(
            evidence,
            ExecutionMissionCompleted,
        ):
            raise TypeError(
                "push requires ExecutionMissionCompleted."
            )

        self._evidence.append(
            evidence
        )

        return evidence

    def pop(
        self,
    ) -> Optional[ExecutionMissionCompleted]:

        if not self._evidence:
            return None

        return self._evidence.popleft()

    def size(
        self,
    ) -> int:

        return len(
            self._evidence
        )