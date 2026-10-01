"""
TODOBA Manual Commercial Activation Admin API.

Privileged boundary for explicitly approved early/manual sales.

Caller authority:
- manual_approval_request_id
- registration_request_id

Server-owned:
- authenticated operator identity
- authoritative customer identity
- Setup Activation identity

This boundary has no payment or settlement authority.
"""

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator

from backend.commercial.customer_manual_commercial_activation_service import (
    CustomerManualCommercialActivationResult,
)


_PATH = "/internal/commercial/manual-activations"


class CustomerManualCommercialActivationAdminRequest(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    manual_approval_request_id: str
    registration_request_id: str

    @field_validator(
        "manual_approval_request_id",
        "registration_request_id",
    )
    @classmethod
    def normalize_required_string(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "value is required."
            )

        return normalized


class CustomerManualCommercialActivationAdminResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    manual_approval_request_id: str
    registration_request_id: str
    customer_id: str
    setup_activation_id: str


def create_customer_manual_commercial_activation_admin_router(
    *,
    commercial_operator_authentication_dependency,
    manual_activation_service,
) -> APIRouter:
    if not callable(
        commercial_operator_authentication_dependency
    ):
        raise TypeError(
            "commercial_operator_authentication_dependency "
            "must be callable."
        )

    approve = getattr(
        manual_activation_service,
        "approve",
        None,
    )

    if not callable(approve):
        raise TypeError(
            "manual_activation_service must expose approve()."
        )

    router = APIRouter()

    @router.post(
        _PATH,
        response_model=(
            CustomerManualCommercialActivationAdminResponse
        ),
    )
    def approve_manual_activation(
        request: CustomerManualCommercialActivationAdminRequest,
        authenticated_operator_id=Depends(
            commercial_operator_authentication_dependency
        ),
    ) -> CustomerManualCommercialActivationAdminResponse:
        result = approve(
            manual_approval_request_id=(
                request.manual_approval_request_id
            ),
            registration_request_id=(
                request.registration_request_id
            ),
            operator_id=authenticated_operator_id,
        )

        if not isinstance(
            result,
            CustomerManualCommercialActivationResult,
        ):
            raise RuntimeError(
                "Manual commercial activation owner "
                "returned an invalid result."
            )

        if (
            result.manual_approval_request_id
            != request.manual_approval_request_id
            or result.registration_request_id
            != request.registration_request_id
        ):
            raise RuntimeError(
                "Manual commercial approval identity "
                "did not converge."
            )

        return (
            CustomerManualCommercialActivationAdminResponse(
                manual_approval_request_id=(
                    result.manual_approval_request_id
                ),
                registration_request_id=(
                    result.registration_request_id
                ),
                customer_id=result.customer_id,
                setup_activation_id=(
                    result.setup_activation_id
                ),
            )
        )

    return router
