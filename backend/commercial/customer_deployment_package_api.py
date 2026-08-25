"""
TODOBA Customer Deployment Package API

Owns the customer HTTP delivery boundary for one
already-published Trusted Agent deployment package.

Trust boundary:

    Authorization: Bearer <customer credential>
        -> authoritative CustomerIdentity
        -> customer-supplied deployment_id
        -> CustomerDeploymentAuthorizer
        -> CustomerDeploymentEntitlementAuthorizer
        -> CustomerDeploymentPackagePublication
        -> TODOBA_Trusted_Agent.ex5

HTTP contract:
- authentication failure is owned by the customer
  authentication dependency and returns HTTP 401
- unknown or cross-customer deployment returns HTTP 404
- missing/suspended entitlement returns HTTP 403
- missing published package returns HTTP 404
- invalid/corrupt published package returns HTTP 500
- successful delivery is application/octet-stream
- download filename is TODOBA_Trusted_Agent.ex5

Security rules:
- customer_id is never accepted from the caller
- agent_id is never accepted from the caller
- package path is never accepted from the caller
- entitlement identity comes from the authoritative deployment
- package identity comes from the authoritative deployment
- unknown and cross-customer deployments converge on one 404
  response to avoid deployment enumeration

This component does not:
- authenticate bearer credentials itself
- issue or revoke customer credentials
- mutate deployment entitlement
- build or publish deployment packages
- access deployment secrets
- process payments or subscriptions
"""

from collections.abc import Callable

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.responses import FileResponse

from backend.commercial.customer_deployment_authorizer import (
    CustomerDeploymentAuthorizer,
)
from backend.commercial.customer_deployment_entitlement_authorizer import (
    CustomerDeploymentEntitlementAuthorizer,
)
from backend.commercial.customer_deployment_package_publication import (
    CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME,
    CustomerDeploymentPackagePublication,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)


_CUSTOMER_DEPLOYMENT_NOT_FOUND_DETAIL = (
    "Customer deployment not found."
)

_CUSTOMER_DEPLOYMENT_ENTITLEMENT_REQUIRED_DETAIL = (
    "Customer deployment entitlement required."
)

_CUSTOMER_DEPLOYMENT_PACKAGE_NOT_FOUND_DETAIL = (
    "Customer deployment package not found."
)

_CUSTOMER_DEPLOYMENT_PACKAGE_INVALID_DETAIL = (
    "Customer deployment package publication is invalid."
)


def create_customer_deployment_package_router(
    *,
    customer_authentication_dependency: (
        Callable[..., CustomerIdentity]
    ),
    deployment_authorizer: (
        CustomerDeploymentAuthorizer
    ),
    entitlement_authorizer: (
        CustomerDeploymentEntitlementAuthorizer
    ),
    package_publication: (
        CustomerDeploymentPackagePublication
    ),
) -> APIRouter:
    """
    Build the customer package delivery router.
    """

    if not callable(
        customer_authentication_dependency
    ):
        raise TypeError(
            "customer_authentication_dependency must "
            "be callable."
        )

    if not isinstance(
        deployment_authorizer,
        CustomerDeploymentAuthorizer,
    ):
        raise TypeError(
            "deployment_authorizer must be "
            "CustomerDeploymentAuthorizer."
        )

    if not isinstance(
        entitlement_authorizer,
        CustomerDeploymentEntitlementAuthorizer,
    ):
        raise TypeError(
            "entitlement_authorizer must be "
            "CustomerDeploymentEntitlementAuthorizer."
        )

    if not isinstance(
        package_publication,
        CustomerDeploymentPackagePublication,
    ):
        raise TypeError(
            "package_publication must be "
            "CustomerDeploymentPackagePublication."
        )

    router = APIRouter()

    @router.get(
        "/customer/deployments/{deployment_id}/package",
        response_class=FileResponse,
    )
    def get_customer_deployment_package(
        deployment_id: str,
        authenticated_customer: CustomerIdentity = Depends(
            customer_authentication_dependency
        ),
    ) -> FileResponse:
        authorized_deployment = (
            deployment_authorizer.authorize(
                authenticated_customer=(
                    authenticated_customer
                ),
                deployment_id=deployment_id,
            )
        )

        if authorized_deployment is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    _CUSTOMER_DEPLOYMENT_NOT_FOUND_DETAIL
                ),
            )

        entitled_deployment = (
            entitlement_authorizer.authorize(
                authorized_deployment=(
                    authorized_deployment
                ),
            )
        )

        if entitled_deployment is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    _CUSTOMER_DEPLOYMENT_ENTITLEMENT_REQUIRED_DETAIL
                ),
            )

        try:
            published_package = (
                package_publication
                .get_published_package(
                    deployment_id=(
                        entitled_deployment.deployment_id
                    )
                )
            )
        except RuntimeError as error:
            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=(
                    _CUSTOMER_DEPLOYMENT_PACKAGE_INVALID_DETAIL
                ),
            ) from error

        if published_package is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    _CUSTOMER_DEPLOYMENT_PACKAGE_NOT_FOUND_DETAIL
                ),
            )

        if (
            published_package.deployment_id
            != entitled_deployment.deployment_id
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=(
                    _CUSTOMER_DEPLOYMENT_PACKAGE_INVALID_DETAIL
                ),
            )

        return FileResponse(
            path=(
                published_package.artifact_path
            ),
            media_type=(
                "application/octet-stream"
            ),
            filename=(
                CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME
            ),
        )

    return router
