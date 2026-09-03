"""
TODOBA Customer Setup Provisioning API

Short-lived authenticated installer orchestration boundary.

Trust flow:

    Authorization: Bearer <R3 setup handoff>
        -> authoritative setup/customer identity
        -> R2 authoritative setup activation
        -> prepare deployment without activation
        -> immutable customer package build request
        -> authoritative package publication evidence
        -> activate deployment only after package READY
        -> activate deployment entitlement
        -> permanently bind R2 setup activation
        -> return customer-safe READY metadata

Asynchronous build boundary:

    package publication missing
        -> HTTP 202
        -> status=build_pending
        -> Windows/offline package worker builds EX5
        -> installer retries the same request

Security rules:
- request accepts only account_fingerprint
- customer_id is never accepted from the caller
- setup_activation_id is never accepted from the caller
- deployment_id is never accepted from the caller
- agent_id is never accepted from the caller
- customer credentials are never issued here
- MetaEditor is never invoked here
- package build is never performed here
- CustomerDeploymentRegistry activation happens only after
  authoritative published-package evidence exists
- BOUND retries never mutate entitlement state
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timezone
from typing import Literal

from fastapi import APIRouter
from fastapi import Header
from fastapi import HTTPException
from fastapi import Response
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapPreparationResult,
    CustomerDeploymentBootstrapResult,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlement,
    CustomerDeploymentEntitlementStatus,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
)
from backend.commercial.customer_deployment_package_publication import (
    CustomerDeploymentPublishedPackage,
)
from backend.commercial.customer_setup_build_continuation_service import (
    CustomerSetupBuildContinuationAuthorization,
    CustomerSetupBuildContinuationIssuanceResult,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffAuthorization,
)


SetupHandoffAuthorizer = Callable[
    [str],
    CustomerSetupHandoffAuthorization | None,
]


_BEARER_PREFIX = "Bearer "

_SECRET_RESPONSE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}

_UNAUTHORIZED_DETAIL = (
    "Customer setup authentication failed."
)

_SETUP_NOT_ACTIVE_DETAIL = (
    "Customer setup activation is not active."
)

_ENTITLEMENT_DETAIL = (
    "Customer deployment entitlement required."
)


class CustomerSetupProvisioningRequest(
    BaseModel
):
    """
    The only customer-controlled provisioning payload.
    """

    model_config = ConfigDict(
        extra="forbid",
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


class CustomerSetupProvisioningResponse(
    BaseModel
):
    """
    Customer-safe provisioning state.

    build_pending intentionally exposes no commercial
    identity or server/package filesystem path.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    status: Literal[
        "build_pending",
        "ready",
    ]

    artifact_sha256: str | None = None
    artifact_size_bytes: int | None = None

    continuation_credential: str | None = Field(
        default=None,
        repr=False,
    )
    continuation_expires_at: str | None = None

    @model_validator(
        mode="after"
    )
    def validate_state(
        self,
    ) -> "CustomerSetupProvisioningResponse":
        has_continuation_credential = (
            self.continuation_credential is not None
        )
        has_continuation_expiry = (
            self.continuation_expires_at is not None
        )

        if (
            has_continuation_credential
            != has_continuation_expiry
        ):
            raise ValueError(
                "Continuation credential and expiry "
                "must appear together."
            )

        if has_continuation_credential:
            if (
                not isinstance(
                    self.continuation_credential,
                    str,
                )
                or not self.continuation_credential
                or self.continuation_credential.strip()
                != self.continuation_credential
            ):
                raise ValueError(
                    "continuation_credential must be "
                    "a non-empty normalized string."
                )

            _validate_continuation_expiry(
                self.continuation_expires_at
            )

        if self.status == "build_pending":
            if (
                self.artifact_sha256 is not None
                or self.artifact_size_bytes is not None
            ):
                raise ValueError(
                    "build_pending response must not "
                    "contain artifact metadata."
                )

            return self

        if has_continuation_credential:
            raise ValueError(
                "ready response must not contain "
                "continuation authority."
            )

        if (
            not isinstance(
                self.artifact_sha256,
                str,
            )
            or len(
                self.artifact_sha256
            ) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in (
                    self.artifact_sha256
                )
            )
        ):
            raise ValueError(
                "ready response requires valid "
                "artifact_sha256."
            )

        if (
            not isinstance(
                self.artifact_size_bytes,
                int,
            )
            or self.artifact_size_bytes <= 0
        ):
            raise ValueError(
                "ready response requires positive "
                "artifact_size_bytes."
            )

        return self


def create_customer_setup_provisioning_router(
    *,
    authorize_setup_handoff: SetupHandoffAuthorizer,
    bootstrap_service,
    build_request_store,
    package_publication,
    entitlement_registry,
    setup_activation_service,
    continuation_service=None,
    clock: Callable[[], datetime] = (
        lambda: datetime.now(
            timezone.utc
        )
    ),
) -> APIRouter:
    """
    Build the asynchronous customer setup provisioning
    router from already-composed authoritative owners.
    """

    if not callable(
        authorize_setup_handoff
    ):
        raise TypeError(
            "authorize_setup_handoff must be callable."
        )

    _require_owner_methods(
        bootstrap_service,
        owner_name="bootstrap_service",
        method_names=(
            "prepare_bootstrap",
            "activate_bootstrap",
        ),
    )

    _require_owner_methods(
        build_request_store,
        owner_name="build_request_store",
        method_names=(
            "register",
        ),
    )

    _require_owner_methods(
        package_publication,
        owner_name="package_publication",
        method_names=(
            "get_published_package",
        ),
    )

    _require_owner_methods(
        entitlement_registry,
        owner_name="entitlement_registry",
        method_names=(
            "activate",
            "is_active",
        ),
    )

    _require_owner_methods(
        setup_activation_service,
        owner_name="setup_activation_service",
        method_names=(
            "get",
            "bind",
        ),
    )

    if continuation_service is not None:
        _require_owner_methods(
            continuation_service,
            owner_name="continuation_service",
            method_names=(
                "issue",
                "authorize",
            ),
        )

        _require_owner_methods(
            bootstrap_service,
            owner_name="bootstrap_service",
            method_names=(
                "recover_prepared_bootstrap",
            ),
        )

    if not callable(
        clock
    ):
        raise TypeError(
            "clock must be callable."
        )

    router = APIRouter()

    @router.post(
        "/customer/setup/provision",
        response_model=(
            CustomerSetupProvisioningResponse
        ),
        response_model_exclude_none=True,
        responses={
            202: {
                "model": (
                    CustomerSetupProvisioningResponse
                )
            }
        },
    )
    def provision_customer_setup(
        request: CustomerSetupProvisioningRequest,
        response: Response,
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> CustomerSetupProvisioningResponse:
        setup_handoff = (
            _extract_setup_handoff_bearer(
                authorization
            )
        )

        try:
            authorization_result = (
                authorize_setup_handoff(
                    setup_handoff
                )
            )
        except ValueError as exc:
            raise _unauthorized_setup_handoff() from exc

        if authorization_result is None:
            raise _unauthorized_setup_handoff()

        if not isinstance(
            authorization_result,
            CustomerSetupHandoffAuthorization,
        ):
            raise RuntimeError(
                "Setup handoff authorizer returned "
                "invalid result."
            )

        customer_id = (
            authorization_result.customer_id
        )

        setup_activation_id = (
            authorization_result
            .setup_activation_id
        )

        activation_before = (
            setup_activation_service.get(
                setup_activation_id=(
                    setup_activation_id
                )
            )
        )

        if activation_before is None:
            raise RuntimeError(
                "Authorized setup activation does not "
                "exist."
            )

        if (
            getattr(
                activation_before,
                "setup_activation_id",
                None,
            )
            != setup_activation_id
        ):
            raise RuntimeError(
                "Authorized setup activation identity "
                "mismatch."
            )

        if (
            getattr(
                activation_before,
                "customer_id",
                None,
            )
            != customer_id
        ):
            raise RuntimeError(
                "Authorized setup activation customer "
                "identity mismatch."
            )

        activation_status = _status_value(
            getattr(
                activation_before,
                "status",
                None,
            )
        )

        if activation_status == "BOUND":
            return _resolve_bound_retry(
                authorization_result=(
                    authorization_result
                ),
                activation=activation_before,
                package_publication=(
                    package_publication
                ),
                entitlement_registry=(
                    entitlement_registry
                ),
            )

        if activation_status == "SUSPENDED":
            raise HTTPException(
                status_code=403,
                detail=(
                    _SETUP_NOT_ACTIVE_DETAIL
                ),
            )

        if activation_status != "ACTIVE":
            raise RuntimeError(
                "Authorized setup activation has "
                "unknown status."
            )

        if (
            authorization_result.deployment_id
            is not None
        ):
            raise RuntimeError(
                "ACTIVE setup handoff unexpectedly "
                "contains deployment identity."
            )

        prepared = (
            bootstrap_service.prepare_bootstrap(
                enrollment_request_id=(
                    setup_activation_id
                ),
                customer_id=customer_id,
                account_fingerprint=(
                    request.account_fingerprint
                ),
            )
        )

        prepared = (
            _require_preparation_result(
                result=prepared,
                setup_activation_id=(
                    setup_activation_id
                ),
                customer_id=customer_id,
                account_fingerprint=(
                    request.account_fingerprint
                ),
            )
        )

        deployment_id = (
            prepared.deployment.deployment_id
        )

        requested_build = (
            CustomerDeploymentPackageBuildRequest(
                deployment_id=deployment_id,
                bootstrap_request_id=(
                    setup_activation_id
                ),
            )
        )

        registered_build = (
            build_request_store.register(
                requested_build
            )
        )

        if not isinstance(
            registered_build,
            CustomerDeploymentPackageBuildRequest,
        ):
            raise RuntimeError(
                "Package build request store returned "
                "invalid result."
            )

        if registered_build != requested_build:
            raise RuntimeError(
                "Package build request identity "
                "did not converge."
            )

        published = (
            package_publication
            .get_published_package(
                deployment_id=deployment_id
            )
        )

        if published is None:
            response.status_code = 202

            if continuation_service is None:
                return (
                    CustomerSetupProvisioningResponse(
                        status="build_pending",
                    )
                )

            current_time = _read_clock(
                clock
            )

            issued_continuation = (
                continuation_service.issue(
                    setup_activation_id=(
                        setup_activation_id
                    ),
                    deployment_id=deployment_id,
                    account_fingerprint=(
                        request.account_fingerprint
                    ),
                    current_time=current_time,
                )
            )

            if not isinstance(
                issued_continuation,
                CustomerSetupBuildContinuationIssuanceResult,
            ):
                raise RuntimeError(
                    "Build continuation owner returned "
                    "invalid issuance result."
                )

            if (
                issued_continuation.setup_activation_id
                != setup_activation_id
                or issued_continuation.deployment_id
                != deployment_id
            ):
                raise RuntimeError(
                    "Build continuation issuance "
                    "identity mismatch."
                )

            for (
                header_name,
                header_value,
            ) in _SECRET_RESPONSE_HEADERS.items():
                response.headers[
                    header_name
                ] = header_value

            return (
                CustomerSetupProvisioningResponse(
                    status="build_pending",
                    continuation_credential=(
                        issued_continuation
                        .continuation_credential
                    ),
                    continuation_expires_at=(
                        issued_continuation.expires_at
                    ),
                )
            )

        return _complete_customer_setup(
            bootstrap_service=bootstrap_service,
            entitlement_registry=(
                entitlement_registry
            ),
            setup_activation_service=(
                setup_activation_service
            ),
            prepared=prepared,
            published=published,
            setup_activation_id=(
                setup_activation_id
            ),
            customer_id=customer_id,
            account_fingerprint=(
                request.account_fingerprint
            ),
            deployment_id=deployment_id,
        )

    if continuation_service is not None:

        @router.post(
            "/customer/setup/continue",
            response_model=(
                CustomerSetupProvisioningResponse
            ),
            response_model_exclude_none=True,
            responses={
                202: {
                    "model": (
                        CustomerSetupProvisioningResponse
                    )
                }
            },
        )
        def continue_customer_setup(
            response: Response,
            authorization: str | None = Header(
                default=None,
                alias="Authorization",
            ),
        ) -> CustomerSetupProvisioningResponse:
            continuation_credential = (
                _extract_setup_handoff_bearer(
                    authorization
                )
            )

            current_time = _read_clock(
                clock
            )

            try:
                continuation_authorization = (
                    continuation_service.authorize(
                        continuation_credential=(
                            continuation_credential
                        ),
                        current_time=current_time,
                    )
                )
            except ValueError as exc:
                raise _unauthorized_setup_handoff() from exc

            if not isinstance(
                continuation_authorization,
                CustomerSetupBuildContinuationAuthorization,
            ):
                raise RuntimeError(
                    "Build continuation owner returned "
                    "invalid authorization result."
                )

            setup_activation_id = (
                continuation_authorization
                .setup_activation_id
            )

            customer_id = (
                continuation_authorization.customer_id
            )

            deployment_id = (
                continuation_authorization.deployment_id
            )

            activation_before = (
                setup_activation_service.get(
                    setup_activation_id=(
                        setup_activation_id
                    )
                )
            )

            if activation_before is None:
                raise RuntimeError(
                    "Authorized setup activation does "
                    "not exist."
                )

            if (
                getattr(
                    activation_before,
                    "setup_activation_id",
                    None,
                )
                != setup_activation_id
            ):
                raise RuntimeError(
                    "Authorized setup activation "
                    "identity mismatch."
                )

            if (
                getattr(
                    activation_before,
                    "customer_id",
                    None,
                )
                != customer_id
            ):
                raise RuntimeError(
                    "Authorized setup activation "
                    "customer identity mismatch."
                )

            activation_status = _status_value(
                getattr(
                    activation_before,
                    "status",
                    None,
                )
            )

            if activation_status == "BOUND":
                return _resolve_bound_retry(
                    authorization_result=(
                        continuation_authorization
                    ),
                    activation=activation_before,
                    package_publication=(
                        package_publication
                    ),
                    entitlement_registry=(
                        entitlement_registry
                    ),
                )

            if activation_status == "SUSPENDED":
                raise HTTPException(
                    status_code=403,
                    detail=(
                        _SETUP_NOT_ACTIVE_DETAIL
                    ),
                )

            if activation_status != "ACTIVE":
                raise RuntimeError(
                    "Authorized setup activation has "
                    "unknown status."
                )

            if (
                getattr(
                    activation_before,
                    "deployment_id",
                    None,
                )
                is not None
            ):
                raise RuntimeError(
                    "ACTIVE setup activation "
                    "unexpectedly contains deployment "
                    "identity."
                )

            recovered = (
                bootstrap_service
                .recover_prepared_bootstrap(
                    enrollment_request_id=(
                        setup_activation_id
                    )
                )
            )

            authoritative_account_fingerprint = (
                getattr(
                    recovered,
                    "account_fingerprint",
                    None,
                )
            )

            if (
                not isinstance(
                    authoritative_account_fingerprint,
                    str,
                )
                or not authoritative_account_fingerprint
                or authoritative_account_fingerprint.strip()
                != authoritative_account_fingerprint
            ):
                raise RuntimeError(
                    "Recovered bootstrap account fingerprint "
                    "is invalid."
                )

            try:
                fingerprint_authorization = (
                    continuation_service.authorize(
                        continuation_credential=(
                            continuation_credential
                        ),
                        current_time=current_time,
                        account_fingerprint=(
                            authoritative_account_fingerprint
                        ),
                    )
                )
            except ValueError as exc:
                raise _unauthorized_setup_handoff() from exc

            if (
                fingerprint_authorization
                != continuation_authorization
            ):
                raise RuntimeError(
                    "Build continuation authorization "
                    "changed during authoritative account "
                    "binding verification."
                )

            recovered = (
                _require_preparation_result(
                    result=recovered,
                    setup_activation_id=(
                        setup_activation_id
                    ),
                    customer_id=customer_id,
                    account_fingerprint=(
                        authoritative_account_fingerprint
                    ),
                )
            )

            if (
                recovered.deployment.deployment_id
                != deployment_id
            ):
                raise RuntimeError(
                    "Recovered bootstrap deployment "
                    "identity does not match "
                    "continuation authority."
                )

            published = (
                package_publication
                .get_published_package(
                    deployment_id=deployment_id
                )
            )

            if published is None:
                response.status_code = 202

                return (
                    CustomerSetupProvisioningResponse(
                        status="build_pending",
                    )
                )

            return _complete_customer_setup(
                bootstrap_service=(
                    bootstrap_service
                ),
                entitlement_registry=(
                    entitlement_registry
                ),
                setup_activation_service=(
                    setup_activation_service
                ),
                prepared=recovered,
                published=published,
                setup_activation_id=(
                    setup_activation_id
                ),
                customer_id=customer_id,
                account_fingerprint=(
                    authoritative_account_fingerprint
                ),
                deployment_id=deployment_id,
            )

    return router


def _complete_customer_setup(
    *,
    bootstrap_service,
    entitlement_registry,
    setup_activation_service,
    prepared: CustomerDeploymentBootstrapPreparationResult,
    published,
    setup_activation_id: str,
    customer_id: str,
    account_fingerprint: str,
    deployment_id: str,
) -> CustomerSetupProvisioningResponse:
    published = (
        _require_published_package(
            published,
            deployment_id=deployment_id,
        )
    )

    activated = (
        bootstrap_service.activate_bootstrap(
            enrollment_request_id=(
                setup_activation_id
            ),
            customer_id=customer_id,
            account_fingerprint=(
                account_fingerprint
            ),
        )
    )

    _require_activation_result(
        result=activated,
        prepared=prepared,
        setup_activation_id=(
            setup_activation_id
        ),
        customer_id=customer_id,
        account_fingerprint=(
            account_fingerprint
        ),
    )

    entitlement = (
        entitlement_registry.activate(
            deployment_id=deployment_id
        )
    )

    _require_active_entitlement(
        entitlement,
        deployment_id=deployment_id,
    )

    bind_result = (
        setup_activation_service.bind(
            setup_activation_id=(
                setup_activation_id
            ),
            deployment_id=deployment_id,
        )
    )

    _require_bound_activation(
        bind_result,
        setup_activation_id=(
            setup_activation_id
        ),
        customer_id=customer_id,
        deployment_id=deployment_id,
    )

    return _ready_response(
        published
    )


def _resolve_bound_retry(
    *,
    authorization_result: (
        CustomerSetupHandoffAuthorization
        | CustomerSetupBuildContinuationAuthorization
    ),
    activation,
    package_publication,
    entitlement_registry,
) -> CustomerSetupProvisioningResponse:
    deployment_id = getattr(
        activation,
        "deployment_id",
        None,
    )

    if not isinstance(
        deployment_id,
        str,
    ) or not deployment_id.strip():
        raise RuntimeError(
            "BOUND customer setup activation is "
            "missing deployment identity."
        )

    deployment_id = deployment_id.strip()

    if (
        authorization_result.deployment_id
        != deployment_id
    ):
        raise RuntimeError(
            "BOUND customer setup handoff deployment "
            "identity mismatch."
        )

    if not entitlement_registry.is_active(
        deployment_id=deployment_id
    ):
        raise HTTPException(
            status_code=403,
            detail=_ENTITLEMENT_DETAIL,
        )

    published = (
        package_publication
        .get_published_package(
            deployment_id=deployment_id
        )
    )

    if published is None:
        raise RuntimeError(
            "BOUND customer setup activation is "
            "missing published package."
        )

    published = _require_published_package(
        published,
        deployment_id=deployment_id,
    )

    return _ready_response(
        published
    )


def _require_preparation_result(
    *,
    result,
    setup_activation_id: str,
    customer_id: str,
    account_fingerprint: str,
) -> CustomerDeploymentBootstrapPreparationResult:
    if not isinstance(
        result,
        CustomerDeploymentBootstrapPreparationResult,
    ):
        raise RuntimeError(
            "Bootstrap preparation returned "
            "invalid result."
        )

    if (
        result.enrollment_request_id
        != setup_activation_id
    ):
        raise RuntimeError(
            "Prepared bootstrap request identity "
            "mismatch."
        )

    if (
        result.deployment.customer_id
        != customer_id
    ):
        raise RuntimeError(
            "Prepared bootstrap customer identity "
            "mismatch."
        )

    if (
        result.account_fingerprint
        != account_fingerprint
    ):
        raise RuntimeError(
            "Prepared bootstrap account identity "
            "mismatch."
        )

    return result


def _require_activation_result(
    *,
    result,
    prepared: (
        CustomerDeploymentBootstrapPreparationResult
    ),
    setup_activation_id: str,
    customer_id: str,
    account_fingerprint: str,
) -> CustomerDeploymentBootstrapResult:
    if not isinstance(
        result,
        CustomerDeploymentBootstrapResult,
    ):
        raise RuntimeError(
            "Bootstrap activation returned "
            "invalid result."
        )

    if (
        result.enrollment_request_id
        != setup_activation_id
    ):
        raise RuntimeError(
            "Activated bootstrap request identity "
            "mismatch."
        )

    if (
        result.deployment.deployment_id
        != prepared.deployment.deployment_id
        or result.deployment.agent_id
        != prepared.deployment.agent_id
        or result.deployment.customer_id
        != customer_id
    ):
        raise RuntimeError(
            "Activated bootstrap deployment "
            "identity mismatch."
        )

    if (
        result.account_fingerprint
        != account_fingerprint
    ):
        raise RuntimeError(
            "Activated bootstrap account identity "
            "mismatch."
        )

    return result


def _require_active_entitlement(
    entitlement,
    *,
    deployment_id: str,
) -> CustomerDeploymentEntitlement:
    if not isinstance(
        entitlement,
        CustomerDeploymentEntitlement,
    ):
        raise RuntimeError(
            "Entitlement activation returned "
            "invalid result."
        )

    if (
        entitlement.deployment_id
        != deployment_id
    ):
        raise RuntimeError(
            "Activated entitlement deployment "
            "identity mismatch."
        )

    if (
        entitlement.status
        is not (
            CustomerDeploymentEntitlementStatus
            .ACTIVE
        )
    ):
        raise RuntimeError(
            "Customer deployment entitlement did "
            "not reach ACTIVE state."
        )

    return entitlement


def _require_bound_activation(
    result,
    *,
    setup_activation_id: str,
    customer_id: str,
    deployment_id: str,
) -> None:
    if (
        getattr(
            result,
            "setup_activation_id",
            None,
        )
        != setup_activation_id
    ):
        raise RuntimeError(
            "Customer setup activation bind identity "
            "mismatch."
        )

    if (
        getattr(
            result,
            "customer_id",
            None,
        )
        != customer_id
    ):
        raise RuntimeError(
            "Customer setup activation bind customer "
            "identity mismatch."
        )

    if (
        getattr(
            result,
            "deployment_id",
            None,
        )
        != deployment_id
    ):
        raise RuntimeError(
            "Customer setup activation bind deployment "
            "identity mismatch."
        )

    if (
        _status_value(
            getattr(
                result,
                "status",
                None,
            )
        )
        != "BOUND"
    ):
        raise RuntimeError(
            "Customer setup activation did not reach "
            "BOUND state."
        )


def _require_published_package(
    result,
    *,
    deployment_id: str,
) -> CustomerDeploymentPublishedPackage:
    if not isinstance(
        result,
        CustomerDeploymentPublishedPackage,
    ):
        raise RuntimeError(
            "Customer package publication returned "
            "invalid result."
        )

    if (
        result.deployment_id
        != deployment_id
    ):
        raise RuntimeError(
            "Customer package publication deployment "
            "identity mismatch."
        )

    return result


def _ready_response(
    published: CustomerDeploymentPublishedPackage,
) -> CustomerSetupProvisioningResponse:
    return CustomerSetupProvisioningResponse(
        status="ready",
        artifact_sha256=(
            published.artifact_sha256
        ),
        artifact_size_bytes=(
            published.artifact_size_bytes
        ),
    )


def _validate_continuation_expiry(
    value,
) -> None:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
        or value.strip() != value
    ):
        raise ValueError(
            "continuation_expires_at must be "
            "a non-empty normalized string."
        )

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError as exc:
        raise ValueError(
            "continuation_expires_at must be "
            "an ISO-8601 timestamp."
        ) from exc

    if parsed.tzinfo is None:
        raise ValueError(
            "continuation_expires_at must be "
            "timezone-aware."
        )


def _read_clock(
    clock: Callable[[], datetime],
) -> datetime:
    value = clock()

    if not isinstance(
        value,
        datetime,
    ):
        raise RuntimeError(
            "Customer setup provisioning clock "
            "returned invalid value."
        )

    if value.tzinfo is None:
        raise RuntimeError(
            "Customer setup provisioning clock "
            "must return timezone-aware datetime."
        )

    return value.astimezone(
        timezone.utc
    )


def _extract_setup_handoff_bearer(
    authorization: str | None,
) -> str:
    if not isinstance(
        authorization,
        str,
    ):
        raise _unauthorized_setup_handoff()

    if not authorization.startswith(
        _BEARER_PREFIX
    ):
        raise _unauthorized_setup_handoff()

    credential = authorization[
        len(_BEARER_PREFIX):
    ]

    if (
        not credential
        or credential.strip()
        != credential
    ):
        raise _unauthorized_setup_handoff()

    return credential


def _unauthorized_setup_handoff(
) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=_UNAUTHORIZED_DETAIL,
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def _status_value(
    status,
) -> str | None:
    value = getattr(
        status,
        "value",
        status,
    )

    if not isinstance(
        value,
        str,
    ):
        return None

    return value


def _require_owner_methods(
    owner,
    *,
    owner_name: str,
    method_names: tuple[str, ...],
) -> None:
    for method_name in method_names:
        if not callable(
            getattr(
                owner,
                method_name,
                None,
            )
        ):
            raise TypeError(
                f"{owner_name} must expose callable "
                f"{method_name}()."
            )
