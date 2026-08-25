"""
TODOBA Customer Onboarding Operator CLI

Offline operator entry point for onboarding one commercial
customer deployment.

Required operating condition:
- TODOBA runtime must be stopped before this command runs

Operator inputs:
- onboarding_request_id
- customer_id
- account_fingerprint
- platform MQL5 root
- MetaEditor executable
- isolated build workspace root

Authoritative configuration:
- control-plane data root comes from backend.config
- customer package root comes from backend.config
- customer deployment master key comes from backend.config
- repository MQL5 source root is fixed by repository layout

Safety:
- onboarding request identity is supplied, never generated here
- the same request id is reused for retries
- deployment secrets are never printed
- account fingerprint is never printed
- server package path is never printed
- one-time customer access credential is printed exactly once
- this CLI never starts or imports backend.main
"""

import argparse
from pathlib import Path

from backend.config import (
    TODOBA_CONTROL_PLANE_DATA_ROOT,
    TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY,
    get_customer_package_root,
)
from backend.commercial.customer_access_credential_registry import (
    CustomerAccessCredentialRegistry,
)
from backend.commercial.customer_access_provisioning_service import (
    CustomerAccessProvisioningService,
    CustomerAccessProvisioningStore,
)
from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapService,
    CustomerDeploymentBootstrapStore,
)
from backend.commercial.customer_deployment_enrollment_service import (
    CustomerDeploymentEnrollmentService,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_master_key import (
    decode_customer_deployment_master_key,
)
from backend.commercial.customer_deployment_package_service import (
    CustomerDeploymentPackageService,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_deployment_runtime_projection import (
    CustomerDeploymentRuntimeProjection,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecretStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_onboarding_service import (
    CustomerOnboardingResult,
    CustomerOnboardingService,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTargetRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)
from scripts.trusted_agent_metaeditor_compiler_runner import (
    MetaEditorCompilerRunner,
)


REPOSITORY_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

REPOSITORY_MQL5_SOURCE_ROOT = (
    REPOSITORY_ROOT
    / "MQL5"
)


def _initialize_if_missing(
    owner,
) -> None:
    """
    Explicit operator-only initialization boundary.

    Cloud runtime remains fail-closed. This helper exists
    only because onboarding is an offline provisioning tool.
    """

    if not owner.is_ready():
        owner.initialize_empty()


def _compose_customer_onboarding_service(
    *,
    control_plane_root: Path,
    encoded_master_key: str,
    mql5_source_root: Path,
    platform_mql5_root: Path,
    workspace_root: Path,
    package_root: Path,
    metaeditor_path: Path,
) -> CustomerOnboardingService:
    """
    Compose the existing authoritative onboarding owners.

    This function does not perform onboarding itself.
    """

    for name, value in (
        (
            "control_plane_root",
            control_plane_root,
        ),
        (
            "mql5_source_root",
            mql5_source_root,
        ),
        (
            "platform_mql5_root",
            platform_mql5_root,
        ),
        (
            "workspace_root",
            workspace_root,
        ),
        (
            "package_root",
            package_root,
        ),
        (
            "metaeditor_path",
            metaeditor_path,
        ),
    ):
        if not isinstance(
            value,
            Path,
        ):
            raise TypeError(
                f"{name} must be Path."
            )

    control_plane_root = (
        control_plane_root.resolve()
    )

    mql5_source_root = (
        mql5_source_root.resolve()
    )

    platform_mql5_root = (
        platform_mql5_root.resolve()
    )

    workspace_root = (
        workspace_root.resolve()
    )

    package_root = (
        package_root.resolve()
    )

    metaeditor_path = (
        metaeditor_path.resolve()
    )

    master_key = (
        decode_customer_deployment_master_key(
            encoded_master_key
        )
    )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    trading_root = (
        control_plane_root
        / "trading"
    )

    deployment_registry = (
        CustomerDeploymentRegistry(
            commercial_root
            / "customer_deployments.json"
        )
    )

    _initialize_if_missing(
        deployment_registry
    )

    secret_store = (
        CustomerDeploymentSecretStore(
            commercial_root
            / "customer_deployment_secrets.json",
            master_key=master_key,
        )
    )

    _initialize_if_missing(
        secret_store
    )

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            trading_root
            / "trusted_agent_account_bindings.json"
        )
    )

    _initialize_if_missing(
        account_binding_store
    )

    credential_registry = (
        TrustedAgentCredentialRegistry()
    )

    execution_signing_key_registry = (
        TrustedAgentSigningKeyRegistry()
    )

    control_signing_key_registry = (
        TrustedAgentSigningKeyRegistry()
    )

    execution_target_registry = (
        ExecutionTargetRegistry()
    )

    runtime_projection = (
        CustomerDeploymentRuntimeProjection(
            deployment_registry=(
                deployment_registry
            ),
            secret_store=secret_store,
            account_binding_store=(
                account_binding_store
            ),
            credential_registry=(
                credential_registry
            ),
            execution_signing_key_registry=(
                execution_signing_key_registry
            ),
            control_signing_key_registry=(
                control_signing_key_registry
            ),
            execution_target_registry=(
                execution_target_registry
            ),
        )
    )

    enrollment_service = (
        CustomerDeploymentEnrollmentService(
            deployment_registry=(
                deployment_registry
            ),
            secret_store=secret_store,
            account_binding_store=(
                account_binding_store
            ),
            runtime_projection=(
                runtime_projection
            ),
        )
    )

    bootstrap_store = (
        CustomerDeploymentBootstrapStore(
            commercial_root
            / "customer_deployment_bootstraps.json"
        )
    )

    _initialize_if_missing(
        bootstrap_store
    )

    bootstrap_service = (
        CustomerDeploymentBootstrapService(
            bootstrap_store=bootstrap_store,
            deployment_registry=(
                deployment_registry
            ),
            secret_store=secret_store,
            account_binding_store=(
                account_binding_store
            ),
            enrollment_service=(
                enrollment_service
            ),
        )
    )

    customer_identity_registry = (
        CustomerIdentityRegistry(
            commercial_root
            / "customer_identities.json"
        )
    )

    _initialize_if_missing(
        customer_identity_registry
    )

    customer_access_credential_registry = (
        CustomerAccessCredentialRegistry(
            commercial_root
            / "customer_access_credentials.json",
            customer_identity_registry=(
                customer_identity_registry
            ),
        )
    )

    _initialize_if_missing(
        customer_access_credential_registry
    )

    entitlement_registry = (
        CustomerDeploymentEntitlementRegistry(
            commercial_root
            / "customer_deployment_entitlements.json",
            deployment_registry=(
                deployment_registry
            ),
        )
    )

    _initialize_if_missing(
        entitlement_registry
    )

    access_provisioning_store = (
        CustomerAccessProvisioningStore(
            commercial_root
            / "customer_access_provisioning.json"
        )
    )

    _initialize_if_missing(
        access_provisioning_store
    )

    access_provisioning_service = (
        CustomerAccessProvisioningService(
            provisioning_store=(
                access_provisioning_store
            ),
            customer_identity_registry=(
                customer_identity_registry
            ),
            credential_registry=(
                customer_access_credential_registry
            ),
            deployment_registry=(
                deployment_registry
            ),
            entitlement_registry=(
                entitlement_registry
            ),
        )
    )

    compiler_runner = (
        MetaEditorCompilerRunner(
            metaeditor_path=(
                metaeditor_path
            )
        )
    )

    package_service = (
        CustomerDeploymentPackageService(
            mql5_source_root=(
                mql5_source_root
            ),
            platform_mql5_root=(
                platform_mql5_root
            ),
            workspace_root=(
                workspace_root
            ),
            package_root=(
                package_root
            ),
            compiler_runner=(
                compiler_runner
            ),
        )
    )

    return CustomerOnboardingService(
        bootstrap_service=(
            bootstrap_service
        ),
        package_service=(
            package_service
        ),
        access_provisioning_service=(
            access_provisioning_service
        ),
    )


def _build_parser(
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Offline TODOBA customer onboarding."
        )
    )

    parser.add_argument(
        "--onboarding-request-id",
        required=True,
        help=(
            "Stable operator request identity. "
            "Reuse the same value when retrying."
        ),
    )

    parser.add_argument(
        "--customer-id",
        required=True,
        help=(
            "Commercial customer identity."
        ),
    )

    parser.add_argument(
        "--account-fingerprint",
        required=True,
        help=(
            "Authoritative target MT5 account fingerprint."
        ),
    )

    parser.add_argument(
        "--platform-mql5-root",
        required=True,
        type=Path,
        help=(
            "MQL5 root of the installed MetaTrader "
            "platform used only for standard libraries."
        ),
    )

    parser.add_argument(
        "--metaeditor-path",
        required=True,
        type=Path,
        help=(
            "Exact MetaEditor executable used for "
            "isolated Trusted Agent compilation."
        ),
    )

    parser.add_argument(
        "--workspace-root",
        required=True,
        type=Path,
        help=(
            "External isolated temporary package-build "
            "workspace root."
        ),
    )

    parser.add_argument(
        "--confirm-runtime-stopped",
        action="store_true",
        required=True,
        help=(
            "Operator confirmation that TODOBA runtime "
            "is stopped before durable onboarding writes."
        ),
    )

    return parser


def _print_safe_result(
    result: CustomerOnboardingResult,
) -> None:
    if not isinstance(
        result,
        CustomerOnboardingResult,
    ):
        raise TypeError(
            "result must be CustomerOnboardingResult."
        )

    print(
        "TODOBA CUSTOMER ONBOARDING COMPLETED"
    )

    print(
        "Onboarding request ID: "
        f"{result.onboarding_request_id}"
    )

    print(
        "Customer ID: "
        f"{result.customer_id}"
    )

    print(
        "Deployment ID: "
        f"{result.deployment_id}"
    )

    print(
        "Agent ID: "
        f"{result.agent_id}"
    )

    print(
        "Credential ID: "
        f"{result.credential_id}"
    )

    print(
        "Package SHA256: "
        f"{result.artifact_sha256}"
    )

    print(
        "Package size bytes: "
        f"{result.artifact_size_bytes}"
    )

    print(
        "SAVE THE FOLLOWING CUSTOMER ACCESS "
        "CREDENTIAL SECURELY."
    )

    print(
        "Customer access credential: "
        f"{result.access_credential}"
    )


def main(
    argv: list[str] | None = None,
) -> None:
    parser = _build_parser()

    arguments = parser.parse_args(
        argv
    )

    if not (
        arguments.confirm_runtime_stopped
    ):
        raise RuntimeError(
            "TODOBA runtime must be stopped "
            "before customer onboarding."
        )

    onboarding_service = (
        _compose_customer_onboarding_service(
            control_plane_root=(
                TODOBA_CONTROL_PLANE_DATA_ROOT
            ),
            encoded_master_key=(
                TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY
            ),
            mql5_source_root=(
                REPOSITORY_MQL5_SOURCE_ROOT
            ),
            platform_mql5_root=(
                arguments.platform_mql5_root
            ),
            workspace_root=(
                arguments.workspace_root
            ),
            package_root=(
                get_customer_package_root()
            ),
            metaeditor_path=(
                arguments.metaeditor_path
            ),
        )
    )

    result = onboarding_service.onboard(
        onboarding_request_id=(
            arguments.onboarding_request_id
        ),
        customer_id=(
            arguments.customer_id
        ),
        account_fingerprint=(
            arguments.account_fingerprint
        ),
    )

    _print_safe_result(
        result
    )


if __name__ == "__main__":
    main()
