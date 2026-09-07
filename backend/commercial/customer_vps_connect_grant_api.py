"""
Customer VPS Connect short-lived grant HTTP boundary.

Customer-controlled request:
- Activation Code
- observed MT5 account fingerprint

Customer-safe response:
- opaque short-lived VPS Connect grant
- expiry

Customer, deployment, Setup Activation, agent, and grant
identities are deliberately absent from the HTTP surface.
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
    field_validator,
)

from backend.commercial.customer_vps_connect_grant_service import (
    CustomerVPSConnectGrantIssuance,
)


_VPS_CONNECT_GRANT_PATH = (
    "/customer/vps-connect/grant"
)

_VPS_CONNECT_REJECTED_DETAIL = (
    "Customer VPS Connect authority could not be verified."
)

_VPS_CONNECT_INTERNAL_DETAIL = (
    "Customer VPS Connect grant issuance failed."
)

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
}


class CustomerVPSConnectGrantRequest(
    BaseModel
):
    """
    The only customer-controlled VPS Connect grant material.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    activation_code: str = Field(
        repr=False,
    )

    account_fingerprint: str

    @field_validator(
        "account_fingerprint"
    )
    @classmethod
    def normalize_account_fingerprint(
        cls,
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "account_fingerprint must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "account_fingerprint is required."
            )

        return normalized


class CustomerVPSConnectGrantResponse(
    BaseModel
):
    """
    Customer-safe short-lived VPS Connect authority.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    grant_credential: str = Field(
        repr=False,
    )

    expires_at: str


def create_customer_vps_connect_grant_router(
    *,
    issue_vps_connect_grant: Callable,
) -> APIRouter:
    """
    Build the customer VPS Connect grant HTTP boundary.

    The injected composition service is the sole business
    authority. This API owns no persistence, deployment,
    provisioning, build, MT5, or VPS mutation.
    """

    if not callable(
        issue_vps_connect_grant
    ):
        raise TypeError(
            "issue_vps_connect_grant must be callable."
        )

    router = APIRouter()

    @router.post(
        _VPS_CONNECT_GRANT_PATH,
        response_model=(
            CustomerVPSConnectGrantResponse
        ),
        status_code=200,
    )
    def issue_customer_vps_connect_grant(
        request: CustomerVPSConnectGrantRequest,
        response: Response,
    ) -> CustomerVPSConnectGrantResponse:
        try:
            result = issue_vps_connect_grant(
                activation_code=(
                    request.activation_code
                ),
                account_fingerprint=(
                    request.account_fingerprint
                ),
            )
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail=(
                    _VPS_CONNECT_REJECTED_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            ) from None
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=(
                    _VPS_CONNECT_INTERNAL_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            ) from None

        if not isinstance(
            result,
            CustomerVPSConnectGrantIssuance,
        ):
            raise HTTPException(
                status_code=500,
                detail=(
                    _VPS_CONNECT_INTERNAL_DETAIL
                ),
                headers=_NO_STORE_HEADERS,
            )

        response.headers[
            "Cache-Control"
        ] = "no-store"

        return CustomerVPSConnectGrantResponse(
            grant_credential=(
                result.grant_credential
            ),
            expires_at=(
                result.expires_at.isoformat()
            ),
        )

    return router
