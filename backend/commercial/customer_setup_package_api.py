"""
TODOBA Customer Setup Package API

Short-lived installer package-delivery boundary.

Trust flow:

    Authorization: Bearer <setup handoff or build continuation>
        -> authoritative credential-specific setup authorization
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
- setup handoff/continuation authority owns customer/setup identity
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
from datetime import datetime
from datetime import timezone

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
from backend.commercial.customer_setup_build_continuation_service import (
    CustomerSetupBuildContinuationAuthorization,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffAuthorization,
)


_SETUP_PACKAGE_PATH = "/customer/setup/package"

_CONTINUATION_PREFIX = "tdbsc1."

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
    continuation_service=None,
    setup_activation_service=None,
    clock: Callable[[], datetime] = (
        lambda: datetime.now(timezone.utc)
    ),
) -> APIRouter:
    """
    Create the customer setup package delivery router.

    Handoff lifetime remains delegated to the authoritative
    handoff owner. Optional build-continuation lifetime is
    checked by the injected continuation owner using this
    boundary's trusted UTC clock.
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

    continuation_enabled = (
        continuation_service is not None
        or setup_activation_service is not None
    )

    if continuation_enabled:
        if (
            continuation_service is None
            or setup_activation_service is None
        ):
            raise TypeError(
                "continuation_service and "
                "setup_activation_service must be "
                "provided together."
            )

        _require_owner_method(
            continuation_service,
            owner_name="continuation_service",
            method_name="authorize",
        )

        _require_owner_method(
            setup_activation_service,
            owner_name="setup_activation_service",
            method_name="get",
        )

        _require_callable(
            clock,
            name="clock",
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
        setup_credential = (
            _extract_bearer_credential(
                authorization
            )
        )

        if setup_credential.startswith(
            _CONTINUATION_PREFIX
        ):
            if (
                continuation_service is None
                or setup_activation_service is None
            ):
                raise _authentication_error()

            current_time = _read_clock(
                clock
            )

            try:
                setup_authorization = (
                    continuation_service.authorize(
                        continuation_credential=(
                            setup_credential
                        ),
                        current_time=current_time,
                    )
                )
            except ValueError as exc:
                raise _authentication_error() from exc

            if not isinstance(
                setup_authorization,
                CustomerSetupBuildContinuationAuthorization,
            ):
                raise RuntimeError(
                    "Setup build continuation authorizer "
                    "returned invalid result."
                )

            _require_bound_continuation_activation(
                setup_activation_service=(
                    setup_activation_service
                ),
                authorization=(
                    setup_authorization
                ),
            )

        else:
            try:
                setup_authorization = (
                    authorize_setup_handoff(
                        setup_credential
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


def _require_bound_continuation_activation(
    *,
    setup_activation_service,
    authorization: CustomerSetupBuildContinuationAuthorization,
) -> None:
    activation = (
        setup_activation_service.get(
            setup_activation_id=(
                authorization.setup_activation_id
            )
        )
    )

    if activation is None:
        raise RuntimeError(
            "Authorized build continuation is missing "
            "customer setup activation."
        )

    activation_id = getattr(
        activation,
        "setup_activation_id",
        None,
    )

    if (
        activation_id
        != authorization.setup_activation_id
    ):
        raise RuntimeError(
            "Build continuation setup activation "
            "identity mismatch."
        )

    activation_customer_id = getattr(
        activation,
        "customer_id",
        None,
    )

    if (
        activation_customer_id
        != authorization.customer_id
    ):
        raise RuntimeError(
            "Build continuation customer identity "
            "mismatch."
        )

    status = _status_value(
        getattr(
            activation,
            "status",
            None,
        )
    )

    if status == "SUSPENDED":
        raise _authentication_error()

    if status == "ACTIVE":
        raise HTTPException(
            status_code=409,
            detail=_NOT_READY_DETAIL,
        )

    if status != "BOUND":
        raise RuntimeError(
            "Authorized build continuation setup "
            "activation has unsupported status."
        )

    activation_deployment_id = getattr(
        activation,
        "deployment_id",
        None,
    )

    if (
        activation_deployment_id
        != authorization.deployment_id
    ):
        raise RuntimeError(
            "Build continuation deployment identity "
            "mismatch."
        )


def _status_value(
    value,
) -> str | None:
    direct = getattr(
        value,
        "value",
        value,
    )

    if not isinstance(
        direct,
        str,
    ):
        return None

    return direct


def _read_clock(
    clock: Callable[[], datetime],
) -> datetime:
    value = clock()

    if not isinstance(
        value,
        datetime,
    ):
        raise RuntimeError(
            "Customer setup package clock returned "
            "invalid value."
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise RuntimeError(
            "Customer setup package clock must return "
            "timezone-aware datetime."
        )

    return value.astimezone(
        timezone.utc
    )


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
