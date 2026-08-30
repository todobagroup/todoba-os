"""
TODOBA Customer Setup Entry Exchange API

Public exchange boundary between a pre-deployment customer
setup launch credential and the short-lived setup handoff
credential consumed by TODOBA Setup.

HTTP flow:

    Authorization: Bearer <setup launch credential>
        -> authoritative launch authorization
        -> authoritative launch_id + customer_id
        -> CustomerSetupEntryGrantService
        -> short-lived setup handoff credential

Security rules:
- customer_id is never accepted from the HTTP caller
- grant_request_id is never accepted from the HTTP caller
- deployment_id and agent_id are never accepted
- launch credentials are accepted only through Authorization
- launch credentials are never returned
- internal setup activation/handoff identities are not returned
- plaintext handoff credential is returned only in the
  successful response and is excluded from repr()
- secret-bearing responses are marked no-store

This component does not:
- issue setup launch credentials
- persist credentials
- own registration
- own setup activation or handoff state
- own deployment, package, MT5, runtime, or trading state
- compose production dependencies
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timezone

from fastapi import APIRouter
from fastapi import Header
from fastapi import HTTPException
from fastapi import Response
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from backend.commercial.customer_setup_entry_grant_service import (
    CustomerSetupEntryGrantResult,
)
from backend.commercial.customer_setup_launch_credential_service import (
    CustomerSetupLaunchAuthorization,
)


_SETUP_ENTRY_PATH = "/customer/setup/entry"
_BEARER_PREFIX = "Bearer "

_AUTHENTICATION_DETAIL = (
    "Customer setup launch authentication failed."
)

_ENTRY_NOT_AVAILABLE_DETAIL = (
    "Customer setup entry is not available."
)

_SECRET_RESPONSE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}


class CustomerSetupEntryResponse(
    BaseModel
):
    """
    Minimal customer-safe setup entry response.

    handoff_credential must be serialized to the customer but
    is deliberately excluded from repr().
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    handoff_credential: str = Field(
        repr=False
    )
    expires_at: str

    @field_validator(
        "handoff_credential",
        "expires_at",
    )
    @classmethod
    def normalize_required_string(
        cls,
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "Setup entry response values must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Setup entry response value is required."
            )

        return normalized


def create_customer_setup_entry_router(
    *,
    authorize_setup_launch: Callable,
    grant_setup_entry: Callable,
    clock: Callable[[], datetime] = (
        lambda: datetime.now(
            timezone.utc
        )
    ),
) -> APIRouter:
    """
    Create the public setup-entry credential exchange router.

    Both business operations are injected so this HTTP owner
    never constructs or initializes authoritative state.
    """

    _require_callable(
        authorize_setup_launch,
        name="authorize_setup_launch",
    )
    _require_callable(
        grant_setup_entry,
        name="grant_setup_entry",
    )
    _require_callable(
        clock,
        name="clock",
    )

    router = APIRouter()

    @router.post(
        _SETUP_ENTRY_PATH,
        response_model=CustomerSetupEntryResponse,
    )
    def exchange_customer_setup_entry(
        response: Response,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> CustomerSetupEntryResponse:
        launch_credential = (
            _extract_bearer_credential(
                authorization
            )
        )

        current_time = _read_clock(
            clock
        )

        try:
            launch_authorization = (
                authorize_setup_launch(
                    launch_credential=(
                        launch_credential
                    ),
                    current_time=current_time,
                )
            )
        except ValueError as exc:
            raise _authentication_error() from exc

        if not isinstance(
            launch_authorization,
            CustomerSetupLaunchAuthorization,
        ):
            raise RuntimeError(
                "Setup launch authorizer returned "
                "invalid result."
            )

        try:
            grant = grant_setup_entry(
                grant_request_id=(
                    launch_authorization.launch_id
                ),
                customer_id=(
                    launch_authorization.customer_id
                ),
                current_time=current_time,
            )
        except ValueError as exc:
            raise _entry_not_available() from exc

        if not isinstance(
            grant,
            CustomerSetupEntryGrantResult,
        ):
            raise RuntimeError(
                "Setup entry grant owner returned "
                "invalid result."
            )

        if (
            grant.grant_request_id
            != launch_authorization.launch_id
        ):
            raise RuntimeError(
                "Setup entry grant request identity "
                "did not converge."
            )

        if (
            grant.customer_id
            != launch_authorization.customer_id
        ):
            raise RuntimeError(
                "Setup entry grant customer identity "
                "did not converge."
            )

        response.headers.update(
            _SECRET_RESPONSE_HEADERS
        )

        return CustomerSetupEntryResponse(
            handoff_credential=(
                grant.handoff_credential
            ),
            expires_at=grant.expires_at,
        )

    return router


def _extract_bearer_credential(
    authorization: str | None,
) -> str:
    if not isinstance(
        authorization,
        str,
    ):
        raise _authentication_error()

    if not authorization.startswith(
        _BEARER_PREFIX
    ):
        raise _authentication_error()

    credential = authorization[
        len(_BEARER_PREFIX):
    ]

    if (
        not credential
        or credential.strip()
        != credential
    ):
        raise _authentication_error()

    return credential


def _read_clock(
    clock: Callable[[], datetime],
) -> datetime:
    value = clock()

    if not isinstance(
        value,
        datetime,
    ):
        raise RuntimeError(
            "Customer setup entry clock returned "
            "invalid value."
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise RuntimeError(
            "Customer setup entry clock must return "
            "timezone-aware datetime."
        )

    return value.astimezone(
        timezone.utc
    )


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=_AUTHENTICATION_DETAIL,
        headers={
            "WWW-Authenticate": "Bearer",
            **_SECRET_RESPONSE_HEADERS,
        },
    )


def _entry_not_available() -> HTTPException:
    return HTTPException(
        status_code=403,
        detail=_ENTRY_NOT_AVAILABLE_DETAIL,
        headers=dict(
            _SECRET_RESPONSE_HEADERS
        ),
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