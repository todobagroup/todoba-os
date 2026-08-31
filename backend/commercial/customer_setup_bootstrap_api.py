"""
TODOBA Customer Setup Bootstrap Exchange API

Public customer-facing HTTP boundary that exchanges one
one-time PKCE bootstrap authorization for one short-lived
customer setup launch credential.

Trust flow:

    authorization_code
    + code_verifier
    + trusted server clock
        -> trusted Bootstrap Launch Grant owner
        -> setup_launch_credential + expires_at

Safety rules:
- caller never supplies customer_id
- caller never supplies deployment_id or agent_id
- API does not issue or redeem bootstrap authorization itself
- API does not issue launch credentials itself
- API owns no durable store
- authorization code and PKCE verifier are never returned
- setup launch credential is redacted from repr()
- internal authorization/grant identities are never exposed
- business rejection uses one generic public error
- internal failures use one generic public error
- successful and owner-controlled error responses are no-store
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timezone

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Response
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from backend.commercial.customer_setup_bootstrap_launch_grant_service import (
    CustomerSetupBootstrapLaunchGrantResult,
)


_BOOTSTRAP_EXCHANGE_PATH = (
    "/customer/setup/bootstrap/exchange"
)

_BOOTSTRAP_REJECTED_DETAIL = (
    "Customer setup bootstrap is not available."
)

_BOOTSTRAP_INTERNAL_DETAIL = (
    "Customer setup bootstrap failed."
)

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
}


class CustomerSetupBootstrapExchangeRequest(
    BaseModel
):
    """
    Customer-controlled PKCE exchange material only.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    authorization_code: str = Field(
        repr=False,
    )
    code_verifier: str = Field(
        repr=False,
    )


class CustomerSetupBootstrapExchangeResponse(
    BaseModel
):
    """
    Minimal customer bootstrap exchange response.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    setup_launch_credential: str = Field(
        repr=False,
    )
    expires_at: str


def create_customer_setup_bootstrap_router(
    *,
    grant_setup_launch: Callable,
    clock: Callable = (
        lambda: datetime.now(
            timezone.utc
        )
    ),
) -> APIRouter:
    """
    Compose the customer bootstrap exchange HTTP boundary.

    The injected grant owner is the sole business authority.
    """

    _require_callable(
        grant_setup_launch,
        name="grant_setup_launch",
    )
    _require_callable(
        clock,
        name="clock",
    )

    router = APIRouter()

    @router.post(
        _BOOTSTRAP_EXCHANGE_PATH,
        response_model=(
            CustomerSetupBootstrapExchangeResponse
        ),
        status_code=200,
    )
    def exchange_customer_setup_bootstrap(
        request: CustomerSetupBootstrapExchangeRequest,
        response: Response,
    ) -> CustomerSetupBootstrapExchangeResponse:
        current_time = _trusted_current_time(
            clock
        )

        try:
            grant = grant_setup_launch(
                authorization_code=(
                    request.authorization_code
                ),
                code_verifier=(
                    request.code_verifier
                ),
                current_time=current_time,
            )
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail=(
                    _BOOTSTRAP_REJECTED_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            ) from None
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=(
                    _BOOTSTRAP_INTERNAL_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            ) from None

        if not isinstance(
            grant,
            CustomerSetupBootstrapLaunchGrantResult,
        ):
            raise HTTPException(
                status_code=500,
                detail=(
                    _BOOTSTRAP_INTERNAL_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            )

        response.headers[
            "Cache-Control"
        ] = "no-store"

        return (
            CustomerSetupBootstrapExchangeResponse(
                setup_launch_credential=(
                    grant.setup_launch_credential
                ),
                expires_at=(
                    grant.expires_at
                ),
            )
        )

    return router


def _trusted_current_time(
    clock: Callable,
) -> datetime:
    try:
        value = clock()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=_BOOTSTRAP_INTERNAL_DETAIL,
            headers=_NO_STORE_HEADERS,
        ) from None

    if not isinstance(
        value,
        datetime,
    ):
        raise HTTPException(
            status_code=500,
            detail=_BOOTSTRAP_INTERNAL_DETAIL,
            headers=_NO_STORE_HEADERS,
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise HTTPException(
            status_code=500,
            detail=_BOOTSTRAP_INTERNAL_DETAIL,
            headers=_NO_STORE_HEADERS,
        )

    return value.astimezone(
        timezone.utc
    )


def _require_callable(
    value,
    *,
    name: str,
) -> None:
    if not callable(
        value
    ):
        raise TypeError(
            f"{name} must be callable."
        )
