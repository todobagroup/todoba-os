"""
TODOBA Execution Mission Acknowledgement Store

Stores Trusted Agent acknowledgement evidence.

This component owns acknowledgement evidence only.

It does not own mission delivery.
It does not own broker execution.
"""

from collections import deque
from typing import Optional

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)


class ExecutionMissionAcknowledgementStore:
    """
    In-memory store for Trusted Agent acknowledgements.
    """

    def __init__(self) -> None:
        self._acknowledgements: deque[
            ExecutionMissionAcknowledgement
        ] = deque()

    def push(
        self,
        acknowledgement: ExecutionMissionAcknowledgement,
    ) -> ExecutionMissionAcknowledgement:

        if not isinstance(
            acknowledgement,
            ExecutionMissionAcknowledgement,
        ):
            raise TypeError(
                "push requires ExecutionMissionAcknowledgement."
            )

        self._acknowledgements.append(
            acknowledgement
        )

        return acknowledgement

    def pop(
        self,
    ) -> Optional[ExecutionMissionAcknowledgement]:

        if not self._acknowledgements:
            return None

        return self._acknowledgements.popleft()

    def size(self) -> int:
        return len(
            self._acknowledgements
        )