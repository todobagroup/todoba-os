"""
Authenticated customer VND payment-initiation HTTP boundary.

The HTTP caller supplies only:
- initiation_request_id

All authoritative commercial and payment facts are supplied by:
- authenticated CustomerIdentity
- CustomerVndPaymentInitiationService

Explicitly forbidden as HTTP authority:
- customer_id
- account balance / licensed cap
- USD price
- VND amount
- currency
- payment rail
- payment_intent_id
- bank destination

This boundary does not perform reconciliation, settlement,
entitlement, activation, or payment-proof acceptance.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Response
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator

from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)


_PATH = "/customer/payments/vnd/initiate"

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}

_PAYMENT_INITIATION_UNAVAILABLE_DETAIL = (
    "VND payment initiation is not currently available."
)

_PAYMENT_INITIATION_INTERNAL_DETAIL = (
    "VND payment initiation could not be completed."
)


class CustomerVndPaymentInitiationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    initiation_request_id: str

    @field_validator(
        "initiation_request_id"
    )
    @classmethod
    def validate_initiation_request_id(
        cls,
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "initiation_request_id must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "initiation_request_id is required."
            )

        return normalized


class CustomerVndPaymentInitiationResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    payment_intent_id: str
    order_id: str

    bank_code: str
    account_number: str
    account_name: str

    amount_minor: int
    currency: str

    transfer_reference: str


def create_customer_vnd_payment_initiation_router(
    *,
    initiate_vnd_payment: Callable,
    customer_authentication_dependency: Callable,
) -> APIRouter:
    """
    Compose authenticated customer VND payment initiation.

    The injected initiation callable is the sole business
    authority. HTTP never derives or accepts monetary truth.
    """

    if not callable(
        initiate_vnd_payment
    ):
        raise TypeError(
            "initiate_vnd_payment must be callable."
        )

    if not callable(
        customer_authentication_dependency
    ):
        raise TypeError(
            "customer_authentication_dependency "
            "must be callable."
        )

    router = APIRouter()

    @router.post(
        _PATH,
        response_model=(
            CustomerVndPaymentInitiationResponse
        ),
        status_code=200,
    )
    def initiate_customer_vnd_payment(
        request: CustomerVndPaymentInitiationRequest,
        response: Response,
        authenticated_customer: CustomerIdentity = Depends(
            customer_authentication_dependency
        ),
    ) -> CustomerVndPaymentInitiationResponse:
        try:
            result = initiate_vnd_payment(
                initiation_request_id=(
                    request.initiation_request_id
                ),
                authenticated_customer=(
                    authenticated_customer
                ),
            )
        except (
            ValueError,
            RuntimeError,
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    _PAYMENT_INITIATION_UNAVAILABLE_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            ) from None
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=(
                    _PAYMENT_INITIATION_INTERNAL_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            ) from None

        try:
            instruction = result.instruction

            payload = (
                CustomerVndPaymentInitiationResponse(
                    payment_intent_id=(
                        instruction.payment_intent_id
                    ),
                    order_id=(
                        instruction.order_id
                    ),
                    bank_code=(
                        instruction.bank_code
                    ),
                    account_number=(
                        instruction.account_number
                    ),
                    account_name=(
                        instruction.account_name
                    ),
                    amount_minor=(
                        instruction.amount_minor
                    ),
                    currency=(
                        instruction.currency
                    ),
                    transfer_reference=(
                        instruction.transfer_reference
                    ),
                )
            )
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=(
                    _PAYMENT_INITIATION_INTERNAL_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            ) from None

        for name, value in _NO_STORE_HEADERS.items():
            response.headers[
                name
            ] = value

        return payload

    return router
