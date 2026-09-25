from pathlib import Path
import importlib.util

import pytest

from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_legacy_execution_compatibility_registry import (
    CustomerLegacyExecutionCompatibilityRegistry,
)


PROVISIONER_PATH = Path(
    "scripts/"
    "provision_customer_legacy_execution_compatibility_registry.py"
)

DEPLOYMENT_FILENAME = "customer_deployments.json"
COMPATIBILITY_FILENAME = (
    "customer_legacy_execution_compatibility.json"
)


def _load_provisioner():
    assert PROVISIONER_PATH.is_file(), (
        "Dedicated legacy compatibility provisioner "
        "does not exist."
    )

    spec = importlib.util.spec_from_file_location(
        "provision_customer_legacy_execution_compatibility_registry",
        PROVISIONER_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare_deployment_authority(
    control_plane_root: Path,
) -> CustomerDeploymentRegistry:
    commercial_root = control_plane_root / "commercial"
    commercial_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    registry = CustomerDeploymentRegistry(
        commercial_root / DEPLOYMENT_FILENAME
    )
    registry.initialize_empty()

    return registry


def test_requires_explicit_runtime_stopped_confirmation(
    tmp_path: Path,
) -> None:
    module = _load_provisioner()

    with pytest.raises(
        RuntimeError,
        match="runtime is stopped",
    ):
        module.provision_customer_legacy_execution_compatibility_registry(
            control_plane_root=tmp_path,
            confirm_runtime_stopped=False,
        )


def test_requires_existing_customer_deployment_authority(
    tmp_path: Path,
) -> None:
    module = _load_provisioner()

    compatibility_path = (
        tmp_path
        / "commercial"
        / COMPATIBILITY_FILENAME
    )

    with pytest.raises(
        RuntimeError,
        match="deployment registry must already exist",
    ):
        module.provision_customer_legacy_execution_compatibility_registry(
            control_plane_root=tmp_path,
            confirm_runtime_stopped=True,
        )

    assert not compatibility_path.exists()


def test_provisions_empty_compatibility_substrate(
    tmp_path: Path,
) -> None:
    module = _load_provisioner()

    deployment_registry = (
        _prepare_deployment_authority(
            tmp_path
        )
    )

    compatibility_path = (
        module
        .provision_customer_legacy_execution_compatibility_registry(
            control_plane_root=tmp_path,
            confirm_runtime_stopped=True,
        )
    )

    assert compatibility_path == (
        tmp_path
        / "commercial"
        / COMPATIBILITY_FILENAME
    )

    assert compatibility_path.is_file()

    restored = (
        CustomerLegacyExecutionCompatibilityRegistry(
            compatibility_path,
            deployment_registry=deployment_registry,
        )
    )

    assert restored.is_ready()


def test_retry_preserves_existing_compatibility_state_byte_for_byte(
    tmp_path: Path,
) -> None:
    module = _load_provisioner()

    _prepare_deployment_authority(
        tmp_path
    )

    first_path = (
        module
        .provision_customer_legacy_execution_compatibility_registry(
            control_plane_root=tmp_path,
            confirm_runtime_stopped=True,
        )
    )

    durable_before = first_path.read_bytes()

    second_path = (
        module
        .provision_customer_legacy_execution_compatibility_registry(
            control_plane_root=tmp_path,
            confirm_runtime_stopped=True,
        )
    )

    assert second_path == first_path
    assert second_path.read_bytes() == durable_before


def test_provisioner_has_no_enrollment_or_recovery_authority() -> None:
    assert PROVISIONER_PATH.is_file()

    source = PROVISIONER_PATH.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )

    assert (
        "customer_deployment_registry.initialize_empty()"
        not in source
    )

    assert (
        "legacy_execution_compatibility_registry.register("
        not in source
    )

    assert (
        "CustomerLegacyExecutionCompatibilityRecord("
        not in source
    )

    assert (
        "CustomerLegacyExecutionCompatibilityRecoveryService"
        not in source
    )
