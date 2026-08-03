"""
TODOBA Broker Execution Evidence API

Receives broker execution evidence from Trusted Agents.

This API owns transport only.

Storage belongs to BrokerExecutionEvidenceStore.
"""

from fastapi import APIRouter

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)

from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)


def create_broker_execution_evidence_router(
    store: BrokerExecutionEvidenceStore,
) -> APIRouter:

    if not isinstance(
        store,
        BrokerExecutionEvidenceStore,
    ):
        raise TypeError(
            "create_broker_execution_evidence_router "
            "requires BrokerExecutionEvidenceStore."
        )

    router = APIRouter()

    @router.post(
        "/broker/evidence"
    )
    def receive_broker_evidence(
        evidence: BrokerExecutionEvidence,
    ):

        store.push(
            evidence
        )

        return {
            "status": "stored",
            "mission_id": evidence.mission_id,
            "store_size": store.size(),
        }

    return router