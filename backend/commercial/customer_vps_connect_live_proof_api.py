"""
TODOBA Customer VPS Connect Live Proof HTTP API.

Exposes customer-safe VPS runtime verification through
a short-lived VPS Connect grant credential.

The injected live-proof service remains the sole business
authority.
"""

from collections.abc import Callable
from typing import Literal

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

from backend.commercial.customer_vps_connect_live_proof_service import (
    CustomerVPSConnectLiveProofResult,
)


_VPS_CONNECT_LIVE_PROOF_PATH = (
    "/customer/vps-connect/live-proof"
)

_VPS_CONNECT_REJECTED_DETAIL = (
    "VPS Connect authorization was rejected."
)

_VPS_CONNECT_INTERNAL_DETAIL = (
    "VPS Connect live proof is unavailable."
)

_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
}


class CustomerVPSConnectLiveProofRequest(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    grant_credential: str = Field(
        repr=False,
    )

    @field_validator(
        "grant_credential"
    )
    @classmethod
    def validate_grant_credential(
        cls,
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "grant_credential must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "grant_credential is required."
            )

        return normalized


class CustomerVPSConnectLiveProofResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    status: Literal[
        "runtime_ready",
        "vps_pending",
        "vps_online",
    ]


def create_customer_vps_connect_live_proof_router(
    *,
    verify_vps_connect_live_proof: Callable,
) -> APIRouter:
    if not callable(
        verify_vps_connect_live_proof
    ):
        raise TypeError(
            "verify_vps_connect_live_proof "
            "must be callable."
        )

    router = APIRouter()

    @router.post(
        _VPS_CONNECT_LIVE_PROOF_PATH,
        response_model=(
            CustomerVPSConnectLiveProofResponse
        ),
        status_code=200,
    )
    def verify_customer_vps_connect_live_proof(
        request: CustomerVPSConnectLiveProofRequest,
        response: Response,
    ) -> CustomerVPSConnectLiveProofResponse:
        try:
            result = (
                verify_vps_connect_live_proof(
                    grant_credential=(
                        request.grant_credential
                    ),
                )
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
            CustomerVPSConnectLiveProofResult,
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

        return CustomerVPSConnectLiveProofResponse(
            status=result.status,
        )

    return router