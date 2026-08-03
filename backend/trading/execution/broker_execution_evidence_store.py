"""
TODOBA Broker Execution Evidence Store

Stores broker execution evidence.

This component owns broker evidence storage only.

It does not:
- execute broker orders
- manage missions
- control MT5
- make trading decisions
"""

from collections import deque
from typing import Optional

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)


class BrokerExecutionEvidenceStore:
    """
    In-memory store for broker execution evidence.
    """

    def __init__(self) -> None:
        self._evidence: deque[
            BrokerExecutionEvidence
        ] = deque()

    def push(
        self,
        evidence: BrokerExecutionEvidence,
    ) -> BrokerExecutionEvidence:

        if not isinstance(
            evidence,
            BrokerExecutionEvidence,
        ):
            raise TypeError(
                "push requires BrokerExecutionEvidence."
            )

        self._evidence.append(
            evidence
        )

        return evidence

    def pop(
        self,
    ) -> Optional[BrokerExecutionEvidence]:

        if not self._evidence:
            return None

        return self._evidence.popleft()

    def size(
        self,
    ) -> int:

        return len(
            self._evidence
        )