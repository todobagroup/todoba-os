"""
Authenticated customer PayPal payment-initiation HTTP boundary.

Caller authority:
- initiation_request_id only

Server authority:
- authenticated customer
- current billing cycle
- USD price
- amount_minor
- currency
- payment rail
- PayPal order identity

This boundary owns no settlement, evidence, entitlement,
activation, or payment-proof authority.
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


_PATH = "/customer/payments/paypal/initiate"

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}

_PAYMENT_INITIATION_UNAVAILABLE_DETAIL = (
    "PayPal payment initiation is not currently available."
)

_PAYMENT_INITIATION_INTERNAL_DETAIL = (
    "PayPal payment initiation could not be completed."
)


class CustomerPayPalPaymentInitiationRequest(BaseModel):
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


class CustomerPayPalPaymentInitiationResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    payment_intent_id: str
    order_id: str
    paypal_order_id: str
    approval_url: str
    amount_minor: int
    currency: str


def create_customer_paypal_payment_initiation_router(
    *,
    initiate_paypal_payment: Callable,
    customer_authentication_dependency: Callable,
) -> APIRouter:
    if not callable(
        initiate_paypal_payment
    ):
        raise TypeError(
            "initiate_paypal_payment must be callable."
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
            CustomerPayPalPaymentInitiationResponse
        ),
        status_code=200,
    )
    def initiate_customer_paypal_payment(
        request: CustomerPayPalPaymentInitiationRequest,
        response: Response,
        authenticated_customer: CustomerIdentity = Depends(
            customer_authentication_dependency
        ),
    ) -> CustomerPayPalPaymentInitiationResponse:
        try:
            result = initiate_paypal_payment(
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
            payload = CustomerPayPalPaymentInitiationResponse(
                payment_intent_id=(
                    result.payment_intent.payment_intent_id
                ),
                order_id=(
                    result.order.order_id
                ),
                paypal_order_id=(
                    result.paypal_order.paypal_order_id
                ),
                approval_url=(
                    result.paypal_order.approval_url
                ),
                amount_minor=(
                    result.order.amount_minor
                ),
                currency=(
                    result.order.currency
                ),
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
