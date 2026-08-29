"""
Offline first-provisioning owner for TODOBA customer setup
control-plane durable state.

This script exists only to initialize the authoritative
durable domains required by the customer setup and customer
package-build flow:

- customer_setup_activations.json
- customer_setup_handoffs.json
- customer_deployment_bootstraps.json
- customer_deployment_package_build_requests/

Safety contract:
- runtime must be explicitly confirmed stopped
- existing valid durable state is preserved
- missing stores are initialized empty
- retries are idempotent
- no setup activation is granted
- no setup handoff credential is issued
- no customer package build request is registered
- no customer, deployment, account, payment, package, secret,
  entitlement, or runtime state is mutated
- package-build lock state is not provisioned here because it
  is synchronization state owned by the lock manager
- cloud runtime must never call this provisioning helper
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapStore,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequestStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStore,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffStore,
)


_CUSTOMER_SETUP_ACTIVATION_FILENAME = (
    "customer_setup_activations.json"
)

_CUSTOMER_SETUP_HANDOFF_FILENAME = (
    "customer_setup_handoffs.json"
)

_CUSTOMER_DEPLOYMENT_BOOTSTRAP_FILENAME = (
    "customer_deployment_bootstraps.json"
)

_CUSTOMER_PACKAGE_BUILD_REQUEST_DIRECTORY = (
    "customer_deployment_package_build_requests"
)


def provision_customer_setup_control_plane(
    *,
    control_plane_root: Path,
    confirm_runtime_stopped: bool,
) -> tuple[
    Path,
    Path,
    Path,
    Path,
]:
    """
    Initialize missing customer setup durable stores and the
    immutable customer package-build request queue.

    Existing valid state is loaded and preserved.

    This function does not create setup rights, credentials,
    or package-build requests.
    """

    if not isinstance(
        control_plane_root,
        Path,
    ):
        raise TypeError(
            "control_plane_root must be Path."
        )

    if confirm_runtime_stopped is not True:
        raise RuntimeError(
            "Customer setup control-plane provisioning "
            "requires explicit confirmation that TODOBA "
            "runtime is stopped."
        )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    activation_storage_path = (
        commercial_root
        / _CUSTOMER_SETUP_ACTIVATION_FILENAME
    )

    handoff_storage_path = (
        commercial_root
        / _CUSTOMER_SETUP_HANDOFF_FILENAME
    )

    bootstrap_storage_path = (
        commercial_root
        / _CUSTOMER_DEPLOYMENT_BOOTSTRAP_FILENAME
    )

    package_build_request_storage_root = (
        commercial_root
        / _CUSTOMER_PACKAGE_BUILD_REQUEST_DIRECTORY
    )

    activation_store = (
        CustomerSetupActivationStore(
            activation_storage_path
        )
    )

    handoff_store = (
        CustomerSetupHandoffStore(
            handoff_storage_path
        )
    )

    bootstrap_store = (
        CustomerDeploymentBootstrapStore(
            bootstrap_storage_path
        )
    )

    package_build_request_store = (
        CustomerDeploymentPackageBuildRequestStore(
            package_build_request_storage_root
        )
    )

    if not activation_store.is_ready():
        activation_store.initialize_empty()

    if not handoff_store.is_ready():
        handoff_store.initialize_empty()

    if not bootstrap_store.is_ready():
        bootstrap_store.initialize_empty()

    if not package_build_request_store.is_ready():
        package_build_request_store.initialize_empty()

    if not activation_store.is_ready():
        raise RuntimeError(
            "Customer setup activation store did not "
            "become ready."
        )

    if not handoff_store.is_ready():
        raise RuntimeError(
            "Customer setup handoff store did not "
            "become ready."
        )

    if not bootstrap_store.is_ready():
        raise RuntimeError(
            "Customer deployment bootstrap store did not "
            "become ready."
        )

    if not package_build_request_store.is_ready():
        raise RuntimeError(
            "Customer deployment package build request "
            "store did not become ready."
        )

    return (
        activation_storage_path,
        handoff_storage_path,
        bootstrap_storage_path,
        package_build_request_storage_root,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Provision TODOBA customer setup durable "
            "control-plane state."
        )
    )

    parser.add_argument(
        "--control-plane-root",
        required=True,
        type=Path,
        help=(
            "TODOBA control-plane data root containing "
            "the commercial directory."
        ),
    )

    parser.add_argument(
        "--confirm-runtime-stopped",
        action="store_true",
        required=True,
        help=(
            "Explicit operator confirmation that TODOBA "
            "runtime is stopped."
        ),
    )

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    (
        activation_storage_path,
        handoff_storage_path,
        bootstrap_storage_path,
        package_build_request_storage_root,
    ) = provision_customer_setup_control_plane(
        control_plane_root=(
            args.control_plane_root
        ),
        confirm_runtime_stopped=(
            args.confirm_runtime_stopped
        ),
    )

    print(
        "CUSTOMER_SETUP_ACTIVATION_STORE=READY"
    )

    print(
        "CUSTOMER_SETUP_HANDOFF_STORE=READY"
    )

    print(
        "CUSTOMER_DEPLOYMENT_BOOTSTRAP_STORE=READY"
    )

    print(
        "CUSTOMER_PACKAGE_BUILD_REQUEST_STORE=READY"
    )

    print(
        "CUSTOMER_SETUP_ACTIVATION_PATH="
        f"{activation_storage_path}"
    )

    print(
        "CUSTOMER_SETUP_HANDOFF_PATH="
        f"{handoff_storage_path}"
    )

    print(
        "CUSTOMER_DEPLOYMENT_BOOTSTRAP_PATH="
        f"{bootstrap_storage_path}"
    )

    print(
        "CUSTOMER_PACKAGE_BUILD_REQUEST_ROOT="
        f"{package_build_request_storage_root}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
