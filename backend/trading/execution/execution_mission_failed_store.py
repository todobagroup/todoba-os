"""
TODOBA Execution Mission Failed Store

Stores Trusted Agent failure evidence.

This component owns failure evidence only.

It does not:
- process lifecycle transitions
- execute broker orders
- manage MT5
"""

from collections import deque
from typing import Optional

from backend.trading.execution.execution_mission_failed import (
    ExecutionMissionFailed,
)


class ExecutionMissionFailedStore:
    """
    In-memory store for execution failure evidence.
    """

    def __init__(self) -> None:
        self._evidence: deque[
            ExecutionMissionFailed
        ] = deque()

    def push(
        self,
        evidence: ExecutionMissionFailed,
    ) -> ExecutionMissionFailed:

        if not isinstance(
            evidence,
            ExecutionMissionFailed,
        ):
            raise TypeError(
                "push requires ExecutionMissionFailed."
            )

        self._evidence.append(
            evidence
        )

        return evidence

    def pop(
        self,
    ) -> Optional[ExecutionMissionFailed]:

        if not self._evidence:
            return None

        return self._evidence.popleft()

    def size(
        self,
    ) -> int:

        return len(
            self._evidence
        )