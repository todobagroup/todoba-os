"""
TODOBA Customer Setup Package API

Short-lived installer package-delivery boundary.

Trust flow:

    Authorization: Bearer <customer setup handoff>
        -> authoritative R3 handoff authorization
        -> BOUND setup activation deployment identity
        -> customer-to-deployment authorization
        -> deployment entitlement authorization
        -> authoritative published EX5
        -> customer-safe binary download

Security rules:
- deployment_id is never accepted from the HTTP caller
- customer_id is never accepted from the HTTP caller
- agent_id is never accepted from the HTTP caller
- account fingerprint is never accepted by this route
- package path is never accepted from the HTTP caller
- Customer Access Credential is not issued or accepted
- setup handoff authorization owns customer/setup identity
- BOUND setup activation owns deployment identity
- commercial deployment owner validates customer ownership
- ACTIVE deployment entitlement is required
- publication owner validates package filesystem state
- package filesystem paths are never serialized to the client

This component does not:
- issue or rotate customer credentials
- build customer packages
- register package build requests
- activate deployments
- mutate entitlement
- bind setup activations
- initialize durable state
- import backend.main
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter
from fastapi import Header
from fastapi import HTTPException
from fastapi.responses import FileResponse

from backend.commercial.customer_deployment_package_publication import (
    CustomerDeploymentPackagePublication,
    CustomerDeploymentPublishedPackage,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffAuthorization,
)


_SETUP_PACKAGE_PATH = "/customer/setup/package"

_AUTHENTICATION_DETAIL = (
    "Customer setup authentication failed."
)

_NOT_READY_DETAIL = (
    "Customer setup package is not ready."
)

_ENTITLEMENT_DETAIL = (
    "Customer deployment entitlement required."
)

_PACKAGE_NOT_FOUND_DETAIL = (
    "Customer setup package not found."
)


def create_customer_setup_package_router(
    *,
    authorize_setup_handoff: Callable,
    authorize_deployment: Callable,
    authorize_entitlement: Callable,
    package_publication: CustomerDeploymentPackagePublication,
) -> APIRouter:
    """
    Create the short-lived setup-handoff package router.

    Time/lifetime enforcement remains outside this HTTP
    owner. authorize_setup_handoff must already encapsulate
    the authoritative R3 clock boundary.
    """

    _require_callable(
        authorize_setup_handoff,
        name="authorize_setup_handoff",
    )

    _require_callable(
        authorize_deployment,
        name="authorize_deployment",
    )

    _require_callable(
        authorize_entitlement,
        name="authorize_entitlement",
    )

    _require_owner_method(
        package_publication,
        owner_name="package_publication",
        method_name="get_published_package",
    )

    router = APIRouter()

    @router.get(
        _SETUP_PACKAGE_PATH,
        response_class=FileResponse,
    )
    def get_customer_setup_package(
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> FileResponse:
        handoff_credential = (
            _extract_bearer_credential(
                authorization
            )
        )

        try:
            setup_authorization = (
                authorize_setup_handoff(
                    handoff_credential
                )
            )
        except ValueError as exc:
            raise _authentication_error() from exc

        if not isinstance(
            setup_authorization,
            CustomerSetupHandoffAuthorization,
        ):
            raise RuntimeError(
                "Setup handoff authorizer returned "
                "invalid result."
            )

        deployment_id = (
            setup_authorization.deployment_id
        )

        if deployment_id is None:
            raise HTTPException(
                status_code=409,
                detail=_NOT_READY_DETAIL,
            )

        authenticated_customer = (
            CustomerIdentity(
                customer_id=(
                    setup_authorization.customer_id
                )
            )
        )

        authorized_deployment = (
            authorize_deployment(
                authenticated_customer=(
                    authenticated_customer
                ),
                deployment_id=deployment_id,
            )
        )

        if authorized_deployment is None:
            raise RuntimeError(
                "Bound customer setup deployment "
                "authorization did not converge."
            )

        authoritative_deployment_id = getattr(
            authorized_deployment,
            "deployment_id",
            None,
        )

        authoritative_customer_id = getattr(
            authorized_deployment,
            "customer_id",
            None,
        )

        if (
            authoritative_deployment_id
            != deployment_id
        ):
            raise RuntimeError(
                "Bound customer setup deployment "
                "identity mismatch."
            )

        if (
            authoritative_customer_id
            != setup_authorization.customer_id
        ):
            raise RuntimeError(
                "Bound customer setup customer "
                "identity mismatch."
            )

        entitled_deployment = (
            authorize_entitlement(
                authorized_deployment=(
                    authorized_deployment
                )
            )
        )

        if entitled_deployment is None:
            raise HTTPException(
                status_code=403,
                detail=_ENTITLEMENT_DETAIL,
            )

        if (
            entitled_deployment
            is not authorized_deployment
        ):
            raise RuntimeError(
                "Customer deployment entitlement "
                "authorization returned different "
                "deployment state."
            )

        published = (
            package_publication
            .get_published_package(
                deployment_id=(
                    authoritative_deployment_id
                )
            )
        )

        if published is None:
            raise HTTPException(
                status_code=404,
                detail=_PACKAGE_NOT_FOUND_DETAIL,
            )

        if not isinstance(
            published,
            CustomerDeploymentPublishedPackage,
        ):
            raise RuntimeError(
                "Customer setup package publication "
                "returned invalid result."
            )

        if (
            published.deployment_id
            != authoritative_deployment_id
        ):
            raise RuntimeError(
                "Customer setup package publication "
                "deployment identity mismatch."
            )

        return FileResponse(
            path=published.artifact_path,
            media_type="application/octet-stream",
            filename=(
                published.artifact_path.name
            ),
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

    prefix = "Bearer "

    if not authorization.startswith(
        prefix
    ):
        raise _authentication_error()

    credential = authorization[
        len(prefix):
    ]

    if (
        not credential
        or credential.strip()
        != credential
    ):
        raise _authentication_error()

    return credential


def _authentication_error(
) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=_AUTHENTICATION_DETAIL,
        headers={
            "WWW-Authenticate": "Bearer",
        },
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


def _require_owner_method(
    owner,
    *,
    owner_name: str,
    method_name: str,
) -> None:
    method = getattr(
        owner,
        method_name,
        None,
    )

    if not callable(
        method
    ):
        raise TypeError(
            f"{owner_name} must expose callable "
            f"{method_name}()."
        )
