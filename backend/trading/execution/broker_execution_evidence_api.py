"""
TODOBA Broker Execution Evidence API

Receives broker execution evidence from Trusted Agents.

This API owns HTTP transport only.
Storage and authentication policy belong to separate
capabilities.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)
from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def create_broker_execution_evidence_router(
    store: BrokerExecutionEvidenceStore,
    authenticator: TrustedAgentAuthenticator,
) -> APIRouter:
    if not isinstance(
        store,
        BrokerExecutionEvidenceStore,
    ):
        raise TypeError(
            "create_broker_execution_evidence_router "
            "requires BrokerExecutionEvidenceStore."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_broker_execution_evidence_router "
            "requires TrustedAgentAuthenticator."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/broker/evidence"
    )
    def receive_broker_evidence(
        evidence: BrokerExecutionEvidence,
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        if evidence.agent_id != authenticated_agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Broker execution evidence does not belong "
                    "to authenticated Agent."
                ),
            )

        store.push(
            evidence
        )

        return {
            "status": "stored",
            "mission_id": evidence.mission_id,
            "store_size": store.size(),
        }

    return router