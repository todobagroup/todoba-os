"""
PayPal buyer checkout experience landing boundary.

These routes are UX-only redirect destinations.

They deliberately own no:
- payment verification
- capture execution
- evidence publication
- settlement
- entitlement
- activation
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


_RETURN_PATH = "/commercial/paypal/return"
_CANCEL_PATH = "/commercial/paypal/cancel"

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}


def create_customer_paypal_checkout_experience_router() -> APIRouter:
    router = APIRouter()

    @router.get(
        _RETURN_PATH,
        response_class=HTMLResponse,
        status_code=200,
    )
    def paypal_checkout_return() -> HTMLResponse:
        return HTMLResponse(
            content=(
                "<!doctype html>"
                "<html><head>"
                "<meta charset='utf-8'>"
                "<title>TODOBA PayPal</title>"
                "</head><body>"
                "<h1>PayPal approval received</h1>"
                "<p>"
                "You may return to TODOBA while the payment "
                "is securely verified."
                "</p>"
                "</body></html>"
            ),
            status_code=200,
            headers=_NO_STORE_HEADERS,
        )

    @router.get(
        _CANCEL_PATH,
        response_class=HTMLResponse,
        status_code=200,
    )
    def paypal_checkout_cancel() -> HTMLResponse:
        return HTMLResponse(
            content=(
                "<!doctype html>"
                "<html><head>"
                "<meta charset='utf-8'>"
                "<title>TODOBA PayPal</title>"
                "</head><body>"
                "<h1>PayPal checkout cancelled</h1>"
                "<p>No payment confirmation was created.</p>"
                "</body></html>"
            ),
            status_code=200,
            headers=_NO_STORE_HEADERS,
        )

    return router
