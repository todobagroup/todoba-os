"""
TODOBA Customer Commercial External Funding Evidence API.

Trusted Agents may publish raw MT5 cashflow evidence only.

This boundary:
- authenticates the Trusted Agent
- verifies authoritative Agent/account binding
- reconstructs immutable raw MT5 evidence
- delegates server-side commercial convergence

It does not accept caller-owned commercial identity,
billing-cycle identity, or funding classification.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from pydantic import ConfigDict

from backend.commercial.customer_commercial_external_funding_convergence_service import (
    CustomerCommercialExternalFundingConvergenceService,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)
from backend.trading.lifecycle.mt5_account_cashflow_history_reader import (
    MT5AccountCashflowEvidence,
)


class CustomerCommercialExternalFundingEvidenceRequest(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    account_fingerprint: str
    deal_ticket: int
    deal_time_msc: int
    observed_at: datetime

    cashflow_kind: Literal[
        "balance",
        "credit",
        "charge",
        "correction",
        "bonus",
        "commission",
        "commission_daily",
        "commission_monthly",
        "commission_agent_daily",
        "commission_agent_monthly",
        "interest",
    ]

    raw_deal_type: int
    amount: Decimal

    order_ticket: int = 0
    deal_entry: int = 0
    magic: int = 0
    position_id: int = 0
    deal_reason: int = 0

    volume: float = 0.0
    price: float = 0.0

    symbol: str = ""
    external_id: str = ""
    comment: str = ""


def create_customer_commercial_external_funding_router(
    *,
    convergence_service: CustomerCommercialExternalFundingConvergenceService,
    authenticator: TrustedAgentAuthenticator,
    account_binding_guard: TrustedAgentAccountBindingGuard,
) -> APIRouter:
    if not isinstance(
        convergence_service,
        CustomerCommercialExternalFundingConvergenceService,
    ):
        raise TypeError(
            "convergence_service must be "
            "CustomerCommercialExternalFundingConvergenceService."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "authenticator must be TrustedAgentAuthenticator."
        )

    if not isinstance(
        account_binding_guard,
        TrustedAgentAccountBindingGuard,
    ):
        raise TypeError(
            "account_binding_guard must be "
            "TrustedAgentAccountBindingGuard."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/commercial/external-funding/evidence"
    )
    def publish_external_funding_evidence(
        request: CustomerCommercialExternalFundingEvidenceRequest,
        agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        try:
            account_binding_guard.require_binding(
                agent_id=agent_id,
                account_fingerprint=(
                    request.account_fingerprint
                ),
            )
        except RuntimeError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Trusted Agent account does not match "
                    "authoritative binding."
                ),
            )

        evidence = MT5AccountCashflowEvidence(
            account_fingerprint=(
                request.account_fingerprint
            ),
            deal_ticket=request.deal_ticket,
            deal_time_msc=request.deal_time_msc,
            observed_at=request.observed_at,
            cashflow_kind=request.cashflow_kind,
            raw_deal_type=request.raw_deal_type,
            amount=request.amount,
            order_ticket=request.order_ticket,
            deal_entry=request.deal_entry,
            magic=request.magic,
            position_id=request.position_id,
            deal_reason=request.deal_reason,
            volume=request.volume,
            price=request.price,
            symbol=request.symbol,
            external_id=request.external_id,
            comment=request.comment,
        )

        try:
            record = convergence_service.converge(
                authenticated_agent_id=agent_id,
                evidence=evidence,
            )
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            )

        return {
            "status": "stored",
            "cycle_id": record.cycle_id,
            "account_fingerprint": (
                record.account_fingerprint
            ),
            "deal_ticket": record.deal_ticket,
            "funding_kind": record.funding_kind,
            "amount": str(
                record.amount
            ),
        }

    return router
