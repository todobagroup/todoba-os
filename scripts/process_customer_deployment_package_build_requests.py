"""
TODOBA Customer Deployment Package Build Request Runner

One-shot Windows/offline package-build process.

Production sequence:

1. Read authoritative production configuration.
2. Recover existing durable commercial owners.
3. Fail closed if any required durable owner is not ready.
4. Snapshot the immutable package-build request queue.
5. Process each request through the existing package-build
   worker.
6. Exit after the queue snapshot has been drained.

This runner does not:
- initialize missing durable commercial state
- register package-build requests
- delete package-build requests
- persist mutable worker/DONE state
- activate deployments
- provision customer access
- mutate entitlement
- bind customer setup activation
- authenticate HTTP requests
- import or start backend.main
- run as the API process
- supervise itself
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from backend.config import (
    TODOBA_CONTROL_PLANE_DATA_ROOT,
    TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY,
    get_customer_package_root,
)
from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapService,
    CustomerDeploymentBootstrapStore,
)
from backend.commercial.customer_deployment_enrollment_service import (
    CustomerDeploymentEnrollmentService,
)
from backend.commercial.customer_deployment_master_key import (
    decode_customer_deployment_master_key,
)
from backend.commercial.customer_deployment_package_build_lock import (
    CustomerDeploymentPackageBuildLockManager,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
    CustomerDeploymentPackageBuildRequestStore,
)
from backend.commercial.customer_deployment_package_build_worker import (
    CustomerDeploymentPackageBuildWorker,
    CustomerDeploymentPackageBuildWorkerResult,
    CustomerDeploymentPackageBuildWorkerStatus,
)
from backend.commercial.customer_deployment_package_publication import (
    CustomerDeploymentPackagePublication,
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

_PACKAGE_BUILD_REQUEST_DIRECTORY = (
    "customer_deployment_package_build_requests"
)

_PACKAGE_BUILD_LOCK_DIRECTORY = (
    "customer_deployment_package_build_locks"
)


@dataclass(
    frozen=True,
)
class CustomerDeploymentPackageBuildQueueSummary:
    total: int
    built: int
    already_ready: int
    busy: int

    def __post_init__(
        self,
    ) -> None:
        for name, value in (
            (
                "total",
                self.total,
            ),
            (
                "built",
                self.built,
            ),
            (
                "already_ready",
                self.already_ready,
            ),
            (
                "busy",
                self.busy,
            ),
        ):
            if not isinstance(
                value,
                int,
            ):
                raise TypeError(
                    f"{name} must be int."
                )

            if value < 0:
                raise ValueError(
                    f"{name} must not be negative."
                )

        if (
            self.built
            + self.already_ready
            + self.busy
            != self.total
        ):
            raise ValueError(
                "Package build queue summary counts "
                "must converge to total."
            )


def process_customer_deployment_package_build_requests(
    *,
    build_request_store: (
        CustomerDeploymentPackageBuildRequestStore
    ),
    worker: CustomerDeploymentPackageBuildWorker,
) -> CustomerDeploymentPackageBuildQueueSummary:
    """
    Drain one deterministic immutable queue snapshot.

    BUSY is a safe non-terminal outcome for this invocation.
    A later one-shot invocation may retry it.

    Any malformed state or worker exception fails the entire
    invocation immediately. Remaining requests are not
    processed after a fault.
    """

    _require_callable(
        build_request_store,
        owner_name="build_request_store",
        method_name="all",
    )

    _require_callable(
        worker,
        owner_name="worker",
        method_name="process",
    )

    requests = (
        build_request_store.all()
    )

    if not isinstance(
        requests,
        tuple,
    ):
        raise RuntimeError(
            "Customer package build request store all() "
            "must return a tuple snapshot."
        )

    built = 0
    already_ready = 0
    busy = 0

    for request in requests:
        if not isinstance(
            request,
            CustomerDeploymentPackageBuildRequest,
        ):
            raise RuntimeError(
                "Customer package build request queue "
                "contains invalid request state."
            )

        result = worker.process(
            deployment_id=(
                request.deployment_id
            )
        )

        if not isinstance(
            result,
            CustomerDeploymentPackageBuildWorkerResult,
        ):
            raise RuntimeError(
                "Customer package build worker returned "
                "invalid result."
            )

        if (
            result.deployment_id
            != request.deployment_id
        ):
            raise RuntimeError(
                "Customer package build worker result "
                "deployment identity mismatch."
            )

        if (
            result.status
            == CustomerDeploymentPackageBuildWorkerStatus
            .BUILT
        ):
            built += 1

        elif (
            result.status
            == CustomerDeploymentPackageBuildWorkerStatus
            .ALREADY_READY
        ):
            already_ready += 1

        elif (
            result.status
            == CustomerDeploymentPackageBuildWorkerStatus
            .BUSY
        ):
            busy += 1

        else:
            raise RuntimeError(
                "Customer package build worker returned "
                "unsupported status."
            )

    return CustomerDeploymentPackageBuildQueueSummary(
        total=len(
            requests
        ),
        built=built,
        already_ready=already_ready,
        busy=busy,
    )


def _compose_customer_deployment_package_build_runner(
    *,
    control_plane_root: Path,
    encoded_master_key: str,
    mql5_source_root: Path,
    platform_mql5_root: Path,
    workspace_root: Path,
    package_root: Path,
    metaeditor_path: Path,
) -> tuple[
    CustomerDeploymentPackageBuildRequestStore,
    CustomerDeploymentPackageBuildWorker,
]:
    """
    Compose production package-build owners.

    Durable stores are recovery-only here. Missing state
    fails closed and is never initialized by this runner.
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

    secret_store = (
        CustomerDeploymentSecretStore(
            commercial_root
            / "customer_deployment_secrets.json",
            master_key=master_key,
        )
    )

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            trading_root
            / "trusted_agent_account_bindings.json"
        )
    )

    bootstrap_store = (
        CustomerDeploymentBootstrapStore(
            commercial_root
            / "customer_deployment_bootstraps.json"
        )
    )

    build_request_store = (
        CustomerDeploymentPackageBuildRequestStore(
            commercial_root
            / _PACKAGE_BUILD_REQUEST_DIRECTORY
        )
    )

    for owner_name, owner in (
        (
            "customer deployment registry",
            deployment_registry,
        ),
        (
            "customer deployment secret store",
            secret_store,
        ),
        (
            "Trusted Agent account binding store",
            account_binding_store,
        ),
        (
            "customer deployment bootstrap store",
            bootstrap_store,
        ),
        (
            "customer package build request store",
            build_request_store,
        ),
    ):
        _require_ready_owner(
            owner,
            owner_name=owner_name,
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

    package_publication = (
        CustomerDeploymentPackagePublication(
            package_root=(
                package_root
            )
        )
    )

    build_lock_manager = (
        CustomerDeploymentPackageBuildLockManager(
            commercial_root
            / _PACKAGE_BUILD_LOCK_DIRECTORY
        )
    )

    worker = (
        CustomerDeploymentPackageBuildWorker(
            build_request_store=(
                build_request_store
            ),
            build_lock_manager=(
                build_lock_manager
            ),
            bootstrap_service=(
                bootstrap_service
            ),
            package_service=(
                package_service
            ),
            package_publication=(
                package_publication
            ),
        )
    )

    return (
        build_request_store,
        worker,
    )


def _require_ready_owner(
    owner,
    *,
    owner_name: str,
) -> None:
    _require_callable(
        owner,
        owner_name=owner_name,
        method_name="is_ready",
    )

    if owner.is_ready() is not True:
        raise RuntimeError(
            f"{owner_name} is not initialized."
        )


def _require_callable(
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


def _build_parser(
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Process the provisioned TODOBA customer "
            "deployment package-build request queue once."
        )
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

    return parser


def _print_safe_summary(
    summary: CustomerDeploymentPackageBuildQueueSummary,
) -> None:
    if not isinstance(
        summary,
        CustomerDeploymentPackageBuildQueueSummary,
    ):
        raise TypeError(
            "summary must be "
            "CustomerDeploymentPackageBuildQueueSummary."
        )

    print(
        "TODOBA CUSTOMER PACKAGE BUILD QUEUE COMPLETED"
    )

    print(
        "TOTAL="
        f"{summary.total}"
    )

    print(
        "BUILT="
        f"{summary.built}"
    )

    print(
        "ALREADY_READY="
        f"{summary.already_ready}"
    )

    print(
        "BUSY="
        f"{summary.busy}"
    )


def main(
    argv: list[str] | None = None,
) -> int:
    parser = _build_parser()

    arguments = parser.parse_args(
        argv
    )

    (
        build_request_store,
        worker,
    ) = (
        _compose_customer_deployment_package_build_runner(
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

    summary = (
        process_customer_deployment_package_build_requests(
            build_request_store=(
                build_request_store
            ),
            worker=worker,
        )
    )

    _print_safe_summary(
        summary
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
