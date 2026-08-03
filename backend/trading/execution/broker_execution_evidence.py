"""
TODOBA Broker Execution Evidence

Represents evidence returned from broker execution.

This capability records broker execution facts only.

It does not:
- send orders
- manage missions
- control MT5
- decide trading actions
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerExecutionEvidence:
    """
    Immutable broker execution evidence.
    """

    mission_id: str

    agent_id: str

    success: bool

    retcode: int

    order_ticket: int

    deal_ticket: int

    execution_price: float

    comment: str

    completed_at: str