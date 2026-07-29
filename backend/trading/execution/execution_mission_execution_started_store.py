"""
TODOBA Execution Mission Execution Started Store

Stores Trusted Agent execution started evidence.

This component owns execution start evidence only.

It does not:
- process lifecycle transitions
- execute broker orders
- manage MT5
"""

from collections import deque
from typing import Optional

from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)


class ExecutionMissionExecutionStartedStore:
    """
    In-memory store for execution started evidence.
    """

    def __init__(self) -> None:
        self._evidence: deque[
            ExecutionMissionExecutionStarted
        ] = deque()

    def push(
        self,
        evidence: ExecutionMissionExecutionStarted,
    ) -> ExecutionMissionExecutionStarted:

        if not isinstance(
            evidence,
            ExecutionMissionExecutionStarted,
        ):
            raise TypeError(
                "push requires "
                "ExecutionMissionExecutionStarted."
            )

        self._evidence.append(
            evidence
        )

        return evidence

    def pop(
        self,
    ) -> Optional[ExecutionMissionExecutionStarted]:

        if not self._evidence:
            return None

        return self._evidence.popleft()

    def size(
        self,
    ) -> int:

        return len(
            self._evidence
        )