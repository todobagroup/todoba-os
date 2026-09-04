"""
Customer Setup Activation Code HTTP exchange boundary.

The customer Setup sends only:
- one customer-facing Activation Code
- one locally generated PKCE S256 challenge

The boundary returns only:
- the short-lived internal bootstrap authorization code
- its expiry

Customer identity and Setup Activation identity are deliberately
absent from both HTTP request and response.

This boundary owns no payment, deployment, entitlement, package,
MT5, persistence, or production-composition authority.
"""

from __future__ import annotations

from typing import Callable

from fastapi import (
    APIRouter,
    HTTPException,
    Response,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from backend.commercial.customer_setup_access_code_exchange_service import (
    CustomerSetupAccessCodeExchangeResult,
)


_ACCESS_CODE_EXCHANGE_PATH = (
    "/customer/setup/access-code/exchange"
)

_ACCESS_CODE_REJECTED_DETAIL = (
    "Customer setup activation could not be verified."
)

_ACCESS_CODE_INTERNAL_DETAIL = (
    "Customer setup activation exchange failed."
)

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
}


class CustomerSetupAccessCodeExchangeRequest(
    BaseModel
):
    """
    Minimal customer-controlled exchange material.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    activation_code: str = Field(
        repr=False,
    )

    code_challenge_s256: str = Field(
        repr=False,
    )


class CustomerSetupAccessCodeExchangeResponse(
    BaseModel
):
    """
    Internal bootstrap authorization returned to Setup only.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    authorization_code: str = Field(
        repr=False,
    )

    expires_at: str


def create_customer_setup_access_code_router(
    *,
    exchange_setup_access: Callable,
) -> APIRouter:
    """
    Compose the customer Activation Code HTTP exchange boundary.

    The injected exchange owner is the sole business authority.
    """

    if not callable(
        exchange_setup_access
    ):
        raise TypeError(
            "exchange_setup_access must be callable."
        )

    router = APIRouter()

    @router.post(
        _ACCESS_CODE_EXCHANGE_PATH,
        response_model=(
            CustomerSetupAccessCodeExchangeResponse
        ),
        status_code=200,
    )
    def exchange_customer_setup_access_code(
        request: CustomerSetupAccessCodeExchangeRequest,
        response: Response,
    ) -> CustomerSetupAccessCodeExchangeResponse:
        try:
            result = exchange_setup_access(
                activation_code=(
                    request.activation_code
                ),
                code_challenge_s256=(
                    request.code_challenge_s256
                ),
            )
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail=(
                    _ACCESS_CODE_REJECTED_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            ) from None
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=(
                    _ACCESS_CODE_INTERNAL_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            ) from None

        if not isinstance(
            result,
            CustomerSetupAccessCodeExchangeResult,
        ):
            raise HTTPException(
                status_code=500,
                detail=(
                    _ACCESS_CODE_INTERNAL_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            )

        response.headers[
            "Cache-Control"
        ] = "no-store"

        return (
            CustomerSetupAccessCodeExchangeResponse(
                authorization_code=(
                    result.authorization_code
                ),
                expires_at=(
                    result.expires_at.isoformat()
                ),
            )
        )

    return router