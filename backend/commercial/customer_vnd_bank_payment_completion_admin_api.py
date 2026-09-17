"""
TODOBA Authenticated VND Bank Payment Completion Admin API

Authenticated internal boundary from one authoritative
VND bank reconciliation identity into the existing verified
payment completion orchestration.

Caller authority:
- reconciliation_id only

Server-owned:
- commercial operator authentication

This boundary does not accept:
- customer_id
- order_id
- payment_intent_id
- payment_evidence_id
- amount_minor
- currency
- settlement_id
- activation_request_id
- setup_activation_id
- activation_code
- operator_id
- status
- deployment_id

It does not verify payment, settle payment, or activate Setup
directly. Those authorities remain delegated to the existing
payment completion orchestration.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationResult,
    CustomerSetupActivationStatus,
)


class CustomerVndBankPaymentCompletionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    reconciliation_id: str


class CustomerVndBankPaymentCompletionResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    setup_activation_id: str
    status: CustomerSetupActivationStatus


def create_customer_vnd_bank_payment_completion_admin_router(
    *,
    commercial_operator_authentication_dependency,
    payment_completion_service,
) -> APIRouter:
    if not callable(
        commercial_operator_authentication_dependency
    ):
        raise TypeError(
            "commercial_operator_authentication_dependency "
            "must be callable."
        )

    complete = getattr(
        payment_completion_service,
        "complete",
        None,
    )

    if not callable(complete):
        raise TypeError(
            "payment_completion_service must expose "
            "callable complete()."
        )

    router = APIRouter()

    @router.post(
        "/internal/commercial/vnd-bank/completions",
        response_model=(
            CustomerVndBankPaymentCompletionResponse
        ),
    )
    def complete_vnd_bank_payment(
        request: CustomerVndBankPaymentCompletionRequest,
        _authenticated_operator_id=Depends(
            commercial_operator_authentication_dependency
        ),
    ) -> CustomerVndBankPaymentCompletionResponse:
        result = payment_completion_service.complete(
            reconciliation_id=request.reconciliation_id,
        )

        if not isinstance(
            result,
            CustomerSetupActivationResult,
        ):
            raise RuntimeError(
                "VND bank payment completion returned "
                "invalid setup activation result."
            )

        if not isinstance(
            result.status,
            CustomerSetupActivationStatus,
        ):
            raise RuntimeError(
                "VND bank payment completion returned "
                "invalid setup activation status."
            )

        return CustomerVndBankPaymentCompletionResponse(
            setup_activation_id=result.setup_activation_id,
            status=result.status,
        )

    return router
