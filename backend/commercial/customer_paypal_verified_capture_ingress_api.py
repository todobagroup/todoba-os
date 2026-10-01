"""
TODOBA Customer PayPal Verified Capture Ingress API.

Public PayPal-facing boundary.

The request body remains provider-owned raw webhook material.
This API does not interpret caller-supplied customer, order,
amount, currency, payment-intent, settlement, or activation truth.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi import status


def create_customer_paypal_verified_capture_ingress_router(
    *,
    ingress_service,
) -> APIRouter:
    complete = getattr(
        ingress_service,
        "complete",
        None,
    )

    if not callable(
        complete
    ):
        raise TypeError(
            "ingress_service must expose callable complete()."
        )

    router = APIRouter()

    @router.post(
        "/commercial/paypal/webhook"
    )
    async def receive_paypal_webhook(
        request: Request,
    ):
        try:
            webhook_event = await request.json()
        except Exception as error:
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "PayPal webhook body is invalid."
                ),
            ) from error

        if not isinstance(
            webhook_event,
            dict,
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "PayPal webhook body must be an object."
                ),
            )

        headers = {
            key: value
            for key, value in request.headers.items()
        }

        try:
            complete(
                headers=headers,
                webhook_event=webhook_event,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail="PayPal webhook rejected.",
            ) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=(
                    status.HTTP_502_BAD_GATEWAY
                ),
                detail=(
                    "PayPal verification unavailable."
                ),
            ) from error

        # Deliberately expose no customer/payment/activation truth.
        return {
            "status": "accepted"
        }

    return router
