"""
TODOBA Execution Result Evidence Adapter

Converts execution result data into broker execution evidence.

This component owns transformation only.

It does not:
- execute broker orders
- send HTTP requests
- store evidence
- manage missions
"""

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)


class ExecutionResultEvidenceAdapter:
    """
    Adapter between execution result contract
    and broker evidence contract.
    """

    @staticmethod
    def create_evidence(
        *,
        mission_id: str,
        agent_id: str,
        success: bool,
        retcode: int,
        order_ticket: int,
        deal_ticket: int,
        execution_price: float,
        comment: str,
        completed_at: str,
    ) -> BrokerExecutionEvidence:

        return BrokerExecutionEvidence(
            mission_id=mission_id,
            agent_id=agent_id,
            success=success,
            retcode=retcode,
            order_ticket=order_ticket,
            deal_ticket=deal_ticket,
            execution_price=execution_price,
            comment=comment,
            completed_at=completed_at,
        )