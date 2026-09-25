"""
TODOBA legacy execution compatibility substrate provisioner.

Offline-only owner for provisioning the durable compatibility
registry required by legacy deployment execution authorization.

Safety contract:
- runtime must be explicitly confirmed stopped
- authoritative customer deployment state must already exist
- customer deployment authority is never initialized here
- missing compatibility substrate may be initialized empty
- existing valid compatibility state is restored and preserved
- no compatibility eligibility is enrolled here
- no recovery service is invoked here
- no payment, setup, deployment, or runtime authority is mutated
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_legacy_execution_compatibility_registry import (
    CustomerLegacyExecutionCompatibilityRegistry,
)


_CUSTOMER_DEPLOYMENT_FILENAME = (
    "customer_deployments.json"
)

_CUSTOMER_LEGACY_EXECUTION_COMPATIBILITY_FILENAME = (
    "customer_legacy_execution_compatibility.json"
)


def provision_customer_legacy_execution_compatibility_registry(
    *,
    control_plane_root: Path,
    confirm_runtime_stopped: bool,
) -> Path:
    """
    Provision only the durable legacy compatibility substrate.

    Existing deployment authority is a prerequisite and is
    never created or mutated by this capability.
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
            "Legacy execution compatibility provisioning "
            "requires explicit confirmation that TODOBA "
            "runtime is stopped."
        )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    deployment_storage_path = (
        commercial_root
        / _CUSTOMER_DEPLOYMENT_FILENAME
    )

    compatibility_storage_path = (
        commercial_root
        / _CUSTOMER_LEGACY_EXECUTION_COMPATIBILITY_FILENAME
    )

    customer_deployment_registry = (
        CustomerDeploymentRegistry(
            deployment_storage_path
        )
    )

    if not customer_deployment_registry.is_ready():
        raise RuntimeError(
            "Customer deployment registry must already exist "
            "before legacy execution compatibility provisioning."
        )

    legacy_execution_compatibility_registry = (
        CustomerLegacyExecutionCompatibilityRegistry(
            compatibility_storage_path,
            deployment_registry=(
                customer_deployment_registry
            ),
        )
    )

    if not legacy_execution_compatibility_registry.is_ready():
        legacy_execution_compatibility_registry.initialize_empty()

    if not legacy_execution_compatibility_registry.is_ready():
        raise RuntimeError(
            "Customer legacy execution compatibility registry "
            "did not become ready."
        )

    return compatibility_storage_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Provision TODOBA legacy execution compatibility "
            "durable substrate."
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

    compatibility_storage_path = (
        provision_customer_legacy_execution_compatibility_registry(
            control_plane_root=(
                args.control_plane_root
            ),
            confirm_runtime_stopped=(
                args.confirm_runtime_stopped
            ),
        )
    )

    print(
        "CUSTOMER_LEGACY_EXECUTION_COMPATIBILITY_STORE=READY"
    )
    print(
        "CUSTOMER_LEGACY_EXECUTION_COMPATIBILITY_PATH="
        f"{compatibility_storage_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
