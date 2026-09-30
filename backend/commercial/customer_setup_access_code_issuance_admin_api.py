"""
TODOBA Customer Setup Access-Code Issuance Admin API

Privileged production boundary continuing one authoritative
paid Setup Activation into one customer-visible Activation Code.

Caller authority:
- setup_activation_id only

Server-owned:
- commercial operator authentication
- customer identity
- access-code identity
- access-code secret generation
- activation state validation

Replay does not rotate an already-active code.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator

from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeIssuance,
)


_PATH = "/internal/commercial/setup/access-codes"


class CustomerSetupAccessCodeIssuanceAdminRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    setup_activation_id: str

    @field_validator("setup_activation_id")
    @classmethod
    def normalize_setup_activation_id(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "setup_activation_id is required."
            )

        return normalized


class CustomerSetupAccessCodeIssuanceAdminResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    setup_activation_id: str
    activation_code: str


def create_customer_setup_access_code_issuance_admin_router(
    *,
    commercial_operator_authentication_dependency,
    access_code_service,
) -> APIRouter:
    if not callable(
        commercial_operator_authentication_dependency
    ):
        raise TypeError(
            "commercial_operator_authentication_dependency "
            "must be callable."
        )

    issue_once = getattr(
        access_code_service,
        "issue_once",
        None,
    )

    if not callable(issue_once):
        raise TypeError(
            "access_code_service must own issue_once()."
        )

    router = APIRouter()

    @router.post(
        _PATH,
        response_model=(
            CustomerSetupAccessCodeIssuanceAdminResponse
        ),
    )
    def issue_customer_setup_access_code(
        request: CustomerSetupAccessCodeIssuanceAdminRequest,
        _authenticated_operator_id=Depends(
            commercial_operator_authentication_dependency
        ),
    ) -> CustomerSetupAccessCodeIssuanceAdminResponse:
        try:
            result = issue_once(
                setup_activation_id=(
                    request.setup_activation_id
                )
            )
        except ValueError as error:
            if str(error) == (
                "Unknown customer setup activation."
            ):
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Customer setup activation "
                        "was not found."
                    ),
                ) from error

            if str(error) == (
                "Customer setup activation is not active."
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Customer setup activation "
                        "is not active."
                    ),
                ) from error

            raise
        except RuntimeError as error:
            if str(error) == (
                "An active Setup Activation Code already "
                "exists; refusing replay rotation."
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "An active Setup Activation Code "
                        "already exists."
                    ),
                ) from error

            raise

        if not isinstance(
            result,
            CustomerSetupAccessCodeIssuance,
        ):
            raise RuntimeError(
                "Access-code issuance owner returned "
                "an invalid result."
            )

        if (
            result.setup_activation_id
            != request.setup_activation_id
        ):
            raise RuntimeError(
                "Access-code activation identity "
                "did not converge."
            )

        if (
            not isinstance(result.activation_code, str)
            or not result.activation_code.strip()
        ):
            raise RuntimeError(
                "Access-code issuance returned "
                "an invalid Activation Code."
            )

        return (
            CustomerSetupAccessCodeIssuanceAdminResponse(
                setup_activation_id=(
                    result.setup_activation_id
                ),
                activation_code=(
                    result.activation_code
                ),
            )
        )

    return router
