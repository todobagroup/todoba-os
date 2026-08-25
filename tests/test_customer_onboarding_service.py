import inspect
from pathlib import Path

import pytest

from backend.commercial.customer_access_provisioning_service import (
    CustomerAccessProvisioningResult,
    CustomerAccessProvisioningService,
)
from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapResult,
    CustomerDeploymentBootstrapService,
)
from backend.commercial.customer_deployment_package_service import (
    CustomerDeploymentPackageResult,
    CustomerDeploymentPackageService,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
)
from backend.commercial.customer_onboarding_service import (
    CustomerOnboardingResult,
    CustomerOnboardingService,
)


REQUEST_ID = "onboarding-request-001"
CUSTOMER_ID = "customer-001"
DEPLOYMENT_ID = "deployment-001"
AGENT_ID = "trusted-agent-001"
ACCOUNT_FINGERPRINT = "broker:account-001"

ARTIFACT_SHA256 = "a" * 64
ARTIFACT_PATH = Path(
    "published"
) / "TODOBA_Trusted_Agent.ex5"


def make_bootstrap_result(
    *,
    request_id: str = REQUEST_ID,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str = DEPLOYMENT_ID,
    agent_id: str = AGENT_ID,
    account_fingerprint: str = ACCOUNT_FINGERPRINT,
) -> CustomerDeploymentBootstrapResult:
    deployment = CustomerDeployment(
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
    )

    secrets = CustomerDeploymentSecrets(
        deployment_id=deployment_id,
        agent_secret="test-agent-secret",
        execution_mission_signing_secret=(
            "test-execution-signing-secret"
        ),
        control_mission_signing_secret=(
            "test-control-signing-secret"
        ),
    )

    return CustomerDeploymentBootstrapResult(
        enrollment_request_id=request_id,
        deployment=deployment,
        secrets=secrets,
        account_fingerprint=account_fingerprint,
        projected_deployment_count=1,
    )


def make_package_result(
    *,
    deployment_id: str = DEPLOYMENT_ID,
    agent_id: str = AGENT_ID,
    artifact_sha256: str = ARTIFACT_SHA256,
    artifact_size_bytes: int = 128,
) -> CustomerDeploymentPackageResult:
    return CustomerDeploymentPackageResult(
        deployment_id=deployment_id,
        agent_id=agent_id,
        artifact_path=ARTIFACT_PATH,
        artifact_sha256=artifact_sha256,
        artifact_size_bytes=artifact_size_bytes,
    )


def make_access_result(
    *,
    request_id: str = REQUEST_ID,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str = DEPLOYMENT_ID,
    credential_id: str = "credential-001",
    access_credential: str = (
        "tdbca1.credential-001.one-time-secret"
    ),
) -> CustomerAccessProvisioningResult:
    return CustomerAccessProvisioningResult(
        provisioning_request_id=request_id,
        customer_id=customer_id,
        deployment_id=deployment_id,
        credential_id=credential_id,
        access_credential=access_credential,
    )


class StubBootstrapService(
    CustomerDeploymentBootstrapService
):
    def __init__(
        self,
        *,
        result: CustomerDeploymentBootstrapResult,
        events: list[str],
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.events = events
        self.error = error
        self.calls: list[
            tuple[str, str, str]
        ] = []

    def bootstrap(
        self,
        *,
        enrollment_request_id: str,
        customer_id: str,
        account_fingerprint: str,
    ) -> CustomerDeploymentBootstrapResult:
        self.events.append(
            "bootstrap"
        )

        self.calls.append(
            (
                enrollment_request_id,
                customer_id,
                account_fingerprint,
            )
        )

        if self.error is not None:
            raise self.error

        return self.result


class StubPackageService(
    CustomerDeploymentPackageService
):
    def __init__(
        self,
        *,
        events: list[str],
        published: (
            CustomerDeploymentPackageResult
            | None
        ) = None,
        build_result: (
            CustomerDeploymentPackageResult
            | None
        ) = None,
        lookup_error: Exception | None = None,
        build_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.published = published
        self.build_result = (
            build_result
            if build_result is not None
            else make_package_result()
        )
        self.lookup_error = lookup_error
        self.build_error = build_error

        self.lookup_calls: list[
            tuple[str, str]
        ] = []

        self.build_calls: list[
            CustomerDeploymentBootstrapResult
        ] = []

    def get_published_package(
        self,
        *,
        deployment_id: str,
        agent_id: str,
    ) -> CustomerDeploymentPackageResult | None:
        self.events.append(
            "package_lookup"
        )

        self.lookup_calls.append(
            (
                deployment_id,
                agent_id,
            )
        )

        if self.lookup_error is not None:
            raise self.lookup_error

        return self.published

    def build_package(
        self,
        *,
        bootstrap_result: (
            CustomerDeploymentBootstrapResult
        ),
    ) -> CustomerDeploymentPackageResult:
        self.events.append(
            "package_build"
        )

        self.build_calls.append(
            bootstrap_result
        )

        if self.build_error is not None:
            raise self.build_error

        self.published = (
            self.build_result
        )

        return self.build_result


class StubAccessProvisioningService(
    CustomerAccessProvisioningService
):
    def __init__(
        self,
        *,
        events: list[str],
        results: list[
            CustomerAccessProvisioningResult
        ],
        error: Exception | None = None,
    ) -> None:
        self.events = events
        self.results = list(
            results
        )
        self.error = error

        self.calls: list[
            tuple[str, str, str]
        ] = []

    def provision(
        self,
        *,
        provisioning_request_id: str,
        customer_id: str,
        deployment_id: str,
    ) -> CustomerAccessProvisioningResult:
        self.events.append(
            "access"
        )

        self.calls.append(
            (
                provisioning_request_id,
                customer_id,
                deployment_id,
            )
        )

        if self.error is not None:
            raise self.error

        if not self.results:
            raise AssertionError(
                "No access provisioning result "
                "configured."
            )

        return self.results.pop(
            0
        )


def build_service(
    *,
    bootstrap_result: (
        CustomerDeploymentBootstrapResult
        | None
    ) = None,
    published_package: (
        CustomerDeploymentPackageResult
        | None
    ) = None,
    build_result: (
        CustomerDeploymentPackageResult
        | None
    ) = None,
    access_results: (
        list[
            CustomerAccessProvisioningResult
        ]
        | None
    ) = None,
    bootstrap_error: Exception | None = None,
    package_lookup_error: Exception | None = None,
    package_build_error: Exception | None = None,
    access_error: Exception | None = None,
):
    events: list[str] = []

    bootstrap_service = (
        StubBootstrapService(
            result=(
                bootstrap_result
                if bootstrap_result is not None
                else make_bootstrap_result()
            ),
            events=events,
            error=bootstrap_error,
        )
    )

    package_service = (
        StubPackageService(
            events=events,
            published=published_package,
            build_result=build_result,
            lookup_error=(
                package_lookup_error
            ),
            build_error=(
                package_build_error
            ),
        )
    )

    access_service = (
        StubAccessProvisioningService(
            events=events,
            results=(
                access_results
                if access_results is not None
                else [
                    make_access_result()
                ]
            ),
            error=access_error,
        )
    )

    service = CustomerOnboardingService(
        bootstrap_service=(
            bootstrap_service
        ),
        package_service=(
            package_service
        ),
        access_provisioning_service=(
            access_service
        ),
    )

    return {
        "service": service,
        "events": events,
        "bootstrap": bootstrap_service,
        "package": package_service,
        "access": access_service,
    }


def test_onboarding_result_normalizes_and_redacts_credential(
) -> None:
    result = CustomerOnboardingResult(
        onboarding_request_id=(
            "  request-001  "
        ),
        customer_id="  customer-001  ",
        deployment_id=(
            "  deployment-001  "
        ),
        agent_id=(
            "  trusted-agent-001  "
        ),
        credential_id=(
            "  credential-001  "
        ),
        access_credential=(
            "  one-time-credential  "
        ),
        artifact_sha256=(
            "A" * 64
        ),
        artifact_size_bytes=123,
    )

    assert (
        result.onboarding_request_id
        == "request-001"
    )
    assert (
        result.customer_id
        == "customer-001"
    )
    assert (
        result.deployment_id
        == "deployment-001"
    )
    assert (
        result.agent_id
        == "trusted-agent-001"
    )
    assert (
        result.credential_id
        == "credential-001"
    )
    assert (
        result.access_credential
        == "one-time-credential"
    )
    assert (
        result.artifact_sha256
        == "a" * 64
    )

    rendered = repr(
        result
    )

    assert (
        "one-time-credential"
        not in rendered
    )
    assert (
        "access_credential=<redacted>"
        in rendered
    )


def test_onboard_builds_package_before_access_provisioning(
) -> None:
    context = build_service()

    result = context[
        "service"
    ].onboard(
        onboarding_request_id=(
            REQUEST_ID
        ),
        customer_id=CUSTOMER_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )

    assert context[
        "events"
    ] == [
        "bootstrap",
        "package_lookup",
        "package_build",
        "access",
    ]

    assert (
        result.onboarding_request_id
        == REQUEST_ID
    )
    assert (
        result.customer_id
        == CUSTOMER_ID
    )
    assert (
        result.deployment_id
        == DEPLOYMENT_ID
    )
    assert result.agent_id == AGENT_ID
    assert (
        result.credential_id
        == "credential-001"
    )
    assert (
        result.access_credential
        == (
            "tdbca1.credential-001."
            "one-time-secret"
        )
    )
    assert (
        result.artifact_sha256
        == ARTIFACT_SHA256
    )
    assert (
        result.artifact_size_bytes
        == 128
    )


def test_onboard_passes_normalized_operator_inputs_to_bootstrap(
) -> None:
    context = build_service()

    context[
        "service"
    ].onboard(
        onboarding_request_id=(
            f"  {REQUEST_ID}  "
        ),
        customer_id=(
            f"  {CUSTOMER_ID}  "
        ),
        account_fingerprint=(
            f"  {ACCOUNT_FINGERPRINT}  "
        ),
    )

    assert context[
        "bootstrap"
    ].calls == [
        (
            REQUEST_ID,
            CUSTOMER_ID,
            ACCOUNT_FINGERPRINT,
        )
    ]


def test_existing_published_package_is_reused_without_build(
) -> None:
    existing_package = (
        make_package_result()
    )

    context = build_service(
        published_package=(
            existing_package
        )
    )

    result = context[
        "service"
    ].onboard(
        onboarding_request_id=(
            REQUEST_ID
        ),
        customer_id=CUSTOMER_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )

    assert context[
        "events"
    ] == [
        "bootstrap",
        "package_lookup",
        "access",
    ]

    assert context[
        "package"
    ].build_calls == []

    assert (
        result.artifact_sha256
        == existing_package.artifact_sha256
    )


def test_package_lookup_failure_prevents_access_provisioning(
) -> None:
    context = build_service(
        package_lookup_error=(
            RuntimeError(
                "unsafe published package"
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="unsafe published package",
    ):
        context[
            "service"
        ].onboard(
            onboarding_request_id=(
                REQUEST_ID
            ),
            customer_id=CUSTOMER_ID,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )

    assert context[
        "events"
    ] == [
        "bootstrap",
        "package_lookup",
    ]

    assert context[
        "access"
    ].calls == []


def test_package_build_failure_prevents_access_provisioning(
) -> None:
    context = build_service(
        package_build_error=(
            RuntimeError(
                "compile failed"
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="compile failed",
    ):
        context[
            "service"
        ].onboard(
            onboarding_request_id=(
                REQUEST_ID
            ),
            customer_id=CUSTOMER_ID,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )

    assert context[
        "events"
    ] == [
        "bootstrap",
        "package_lookup",
        "package_build",
    ]

    assert context[
        "access"
    ].calls == []


def test_bootstrap_failure_prevents_package_and_access(
) -> None:
    context = build_service(
        bootstrap_error=(
            RuntimeError(
                "bootstrap failed"
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="bootstrap failed",
    ):
        context[
            "service"
        ].onboard(
            onboarding_request_id=(
                REQUEST_ID
            ),
            customer_id=CUSTOMER_ID,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )

    assert context[
        "events"
    ] == [
        "bootstrap",
    ]


def test_retry_reuses_published_package_and_rotates_one_time_credential(
) -> None:
    first_access = (
        make_access_result(
            credential_id=(
                "credential-stable"
            ),
            access_credential=(
                "tdbca1.credential-stable.secret-one"
            ),
        )
    )

    second_access = (
        make_access_result(
            credential_id=(
                "credential-stable"
            ),
            access_credential=(
                "tdbca1.credential-stable.secret-two"
            ),
        )
    )

    context = build_service(
        access_results=[
            first_access,
            second_access,
        ]
    )

    first = context[
        "service"
    ].onboard(
        onboarding_request_id=(
            REQUEST_ID
        ),
        customer_id=CUSTOMER_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )

    second = context[
        "service"
    ].onboard(
        onboarding_request_id=(
            REQUEST_ID
        ),
        customer_id=CUSTOMER_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )

    assert (
        first.credential_id
        == second.credential_id
        == "credential-stable"
    )

    assert (
        first.access_credential
        != second.access_credential
    )

    assert len(
        context[
            "package"
        ].build_calls
    ) == 1

    assert context[
        "events"
    ] == [
        "bootstrap",
        "package_lookup",
        "package_build",
        "access",
        "bootstrap",
        "package_lookup",
        "access",
    ]


def test_bootstrap_customer_mismatch_fails_before_package_or_access(
) -> None:
    mismatched_bootstrap = (
        make_bootstrap_result(
            customer_id=(
                "customer-other"
            )
        )
    )

    context = build_service(
        bootstrap_result=(
            mismatched_bootstrap
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Bootstrap deployment customer "
            "identity mismatch"
        ),
    ):
        context[
            "service"
        ].onboard(
            onboarding_request_id=(
                REQUEST_ID
            ),
            customer_id=CUSTOMER_ID,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )

    assert context[
        "events"
    ] == [
        "bootstrap",
    ]


def test_package_deployment_mismatch_fails_before_access(
) -> None:
    context = build_service(
        published_package=(
            make_package_result(
                deployment_id=(
                    "deployment-other"
                )
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Published package deployment "
            "identity mismatch"
        ),
    ):
        context[
            "service"
        ].onboard(
            onboarding_request_id=(
                REQUEST_ID
            ),
            customer_id=CUSTOMER_ID,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )

    assert context[
        "events"
    ] == [
        "bootstrap",
        "package_lookup",
    ]

    assert context[
        "access"
    ].calls == []


def test_package_agent_mismatch_fails_before_access(
) -> None:
    context = build_service(
        published_package=(
            make_package_result(
                agent_id=(
                    "trusted-agent-other"
                )
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Published package Trusted Agent "
            "identity mismatch"
        ),
    ):
        context[
            "service"
        ].onboard(
            onboarding_request_id=(
                REQUEST_ID
            ),
            customer_id=CUSTOMER_ID,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )

    assert context[
        "access"
    ].calls == []


def test_access_provisioning_receives_authoritative_deployment_identity(
) -> None:
    context = build_service()

    context[
        "service"
    ].onboard(
        onboarding_request_id=(
            REQUEST_ID
        ),
        customer_id=CUSTOMER_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )

    assert context[
        "access"
    ].calls == [
        (
            REQUEST_ID,
            CUSTOMER_ID,
            DEPLOYMENT_ID,
        )
    ]


def test_access_request_mismatch_fails_closed(
) -> None:
    context = build_service(
        access_results=[
            make_access_result(
                request_id=(
                    "request-other"
                )
            )
        ]
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Access provisioning request "
            "identity mismatch"
        ),
    ):
        context[
            "service"
        ].onboard(
            onboarding_request_id=(
                REQUEST_ID
            ),
            customer_id=CUSTOMER_ID,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )


def test_access_customer_mismatch_fails_closed(
) -> None:
    context = build_service(
        access_results=[
            make_access_result(
                customer_id=(
                    "customer-other"
                )
            )
        ]
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Access provisioning customer "
            "identity mismatch"
        ),
    ):
        context[
            "service"
        ].onboard(
            onboarding_request_id=(
                REQUEST_ID
            ),
            customer_id=CUSTOMER_ID,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )


def test_access_deployment_mismatch_fails_closed(
) -> None:
    context = build_service(
        access_results=[
            make_access_result(
                deployment_id=(
                    "deployment-other"
                )
            )
        ]
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Access provisioning deployment "
            "identity mismatch"
        ),
    ):
        context[
            "service"
        ].onboard(
            onboarding_request_id=(
                REQUEST_ID
            ),
            customer_id=CUSTOMER_ID,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )


def test_onboarding_result_does_not_expose_secret_or_server_path_fields(
) -> None:
    fields = set(
        CustomerOnboardingResult
        .__annotations__
    )

    assert fields == {
        "onboarding_request_id",
        "customer_id",
        "deployment_id",
        "agent_id",
        "credential_id",
        "access_credential",
        "artifact_sha256",
        "artifact_size_bytes",
    }

    assert not (
        {
            "account_fingerprint",
            "artifact_path",
            "agent_secret",
            "execution_mission_signing_secret",
            "control_mission_signing_secret",
        }
        & fields
    )


def test_onboard_signature_exposes_only_operator_identity_inputs(
) -> None:
    signature = inspect.signature(
        CustomerOnboardingService.onboard
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
        "onboarding_request_id",
        "customer_id",
        "account_fingerprint",
    )

    forbidden = {
        "deployment_id",
        "agent_id",
        "credential_id",
        "access_credential",
        "agent_secret",
        "execution_mission_signing_secret",
        "control_mission_signing_secret",
        "artifact_path",
        "package_root",
        "payment_id",
        "subscription_id",
        "http_request",
    }

    assert not (
        forbidden
        & set(
            signature.parameters
        )
    )


def test_service_requires_authoritative_owner_types(
) -> None:
    context = build_service()

    with pytest.raises(
        TypeError,
        match="bootstrap_service",
    ):
        CustomerOnboardingService(
            bootstrap_service=object(),
            package_service=(
                context[
                    "package"
                ]
            ),
            access_provisioning_service=(
                context[
                    "access"
                ]
            ),
        )

    with pytest.raises(
        TypeError,
        match="package_service",
    ):
        CustomerOnboardingService(
            bootstrap_service=(
                context[
                    "bootstrap"
                ]
            ),
            package_service=object(),
            access_provisioning_service=(
                context[
                    "access"
                ]
            ),
        )

    with pytest.raises(
        TypeError,
        match=(
            "access_provisioning_service"
        ),
    ):
        CustomerOnboardingService(
            bootstrap_service=(
                context[
                    "bootstrap"
                ]
            ),
            package_service=(
                context[
                    "package"
                ]
            ),
            access_provisioning_service=(
                object()
            ),
        )
