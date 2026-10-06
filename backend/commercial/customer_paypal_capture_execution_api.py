"""
Authenticated customer PayPal capture-execution HTTP boundary.

Caller authority:
- payment_intent_id only

Server authority:
- authenticated customer
- commercial order ownership
- PayPal rail
- authoritative PayPal order binding
- provider capture identity

This boundary owns no payment proof, evidence, settlement,
entitlement, or Setup activation authority.
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


_PATH = "/customer/payments/paypal/capture"

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}

_CAPTURE_UNAVAILABLE_DETAIL = (
    "PayPal payment capture is not currently available."
)

_CAPTURE_INTERNAL_DETAIL = (
    "PayPal payment capture could not be completed."
)


class CustomerPayPalCaptureExecutionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    payment_intent_id: str

    @field_validator(
        "payment_intent_id"
    )
    @classmethod
    def validate_payment_intent_id(
        cls,
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "payment_intent_id must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "payment_intent_id is required."
            )

        return normalized


class CustomerPayPalCaptureExecutionResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    payment_intent_id: str
    order_id: str
    paypal_order_id: str
    provider_status: str


def create_customer_paypal_capture_execution_router(
    *,
    capture_paypal_payment: Callable,
    customer_authentication_dependency: Callable,
) -> APIRouter:
    if not callable(
        capture_paypal_payment
    ):
        raise TypeError(
            "capture_paypal_payment must be callable."
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
            CustomerPayPalCaptureExecutionResponse
        ),
        status_code=200,
    )
    def capture_customer_paypal_payment(
        request: CustomerPayPalCaptureExecutionRequest,
        response: Response,
        authenticated_customer: CustomerIdentity = Depends(
            customer_authentication_dependency
        ),
    ) -> CustomerPayPalCaptureExecutionResponse:
        try:
            result = capture_paypal_payment(
                payment_intent_id=(
                    request.payment_intent_id
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
                detail=_CAPTURE_UNAVAILABLE_DETAIL,
                headers=_NO_STORE_HEADERS,
            ) from None
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=_CAPTURE_INTERNAL_DETAIL,
                headers=_NO_STORE_HEADERS,
            ) from None

        try:
            payload = (
                CustomerPayPalCaptureExecutionResponse(
                    payment_intent_id=(
                        result.payment_intent_id
                    ),
                    order_id=result.order_id,
                    paypal_order_id=(
                        result.paypal_order_id
                    ),
                    provider_status=(
                        result.provider_status
                    ),
                )
            )
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=_CAPTURE_INTERNAL_DETAIL,
                headers=_NO_STORE_HEADERS,
            ) from None

        for name, value in (
            _NO_STORE_HEADERS.items()
        ):
            response.headers[
                name
            ] = value

        return payload

    return router