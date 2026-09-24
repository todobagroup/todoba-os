from pathlib import Path
import json

import pytest

from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_legacy_execution_compatibility_registry import (
    CustomerLegacyExecutionCompatibilityRecord,
    CustomerLegacyExecutionCompatibilityRegistry,
)


def _ready_deployments(tmp_path):
    registry = CustomerDeploymentRegistry(
        tmp_path / "deployments.json"
    )
    registry.initialize_empty()

    deployment = CustomerDeployment(
        customer_id="customer-001",
        deployment_id="deployment-001",
        agent_id="trusted-agent-001",
    )
    registry.register(deployment)

    return registry, deployment


def _ready_registry(tmp_path):
    deployment_registry, deployment = (
        _ready_deployments(tmp_path)
    )

    registry = CustomerLegacyExecutionCompatibilityRegistry(
        tmp_path / "legacy-execution-compatibility.json",
        deployment_registry=deployment_registry,
    )
    registry.initialize_empty()

    return registry, deployment_registry, deployment


def _record():
    return CustomerLegacyExecutionCompatibilityRecord(
        deployment_id="deployment-001",
        setup_activation_id="setup-activation-001",
        recovery_request_id=(
            "setup-continuity-recovery:deployment-001"
        ),
    )


def test_first_recovery_eligibility_registration_is_durable(
    tmp_path,
) -> None:
    registry, deployment_registry, _ = (
        _ready_registry(tmp_path)
    )

    registered = registry.register(_record())

    restored = CustomerLegacyExecutionCompatibilityRegistry(
        tmp_path / "legacy-execution-compatibility.json",
        deployment_registry=deployment_registry,
    )

    assert registered == _record()
    assert restored.get(
        deployment_id="deployment-001"
    ) == _record()


def test_identical_registration_is_idempotent(
    tmp_path,
) -> None:
    registry, _, _ = _ready_registry(tmp_path)

    first = registry.register(_record())
    second = registry.register(_record())

    assert second is first
    assert registry.size() == 1


def test_conflicting_provenance_is_rejected(
    tmp_path,
) -> None:
    registry, _, _ = _ready_registry(tmp_path)

    registry.register(_record())

    with pytest.raises(
        ValueError,
        match="different recovery provenance",
    ):
        registry.register(
            CustomerLegacyExecutionCompatibilityRecord(
                deployment_id="deployment-001",
                setup_activation_id="setup-activation-OTHER",
                recovery_request_id=(
                    "setup-continuity-recovery:"
                    "deployment-001"
                ),
            )
        )


def test_unknown_deployment_is_rejected(
    tmp_path,
) -> None:
    registry, _, _ = _ready_registry(tmp_path)

    with pytest.raises(
        ValueError,
        match="deployment does not exist",
    ):
        registry.register(
            CustomerLegacyExecutionCompatibilityRecord(
                deployment_id="deployment-missing",
                setup_activation_id="setup-activation-001",
                recovery_request_id=(
                    "setup-continuity-recovery:"
                    "deployment-missing"
                ),
            )
        )


def test_missing_store_is_not_silently_authoritative(
    tmp_path,
) -> None:
    deployment_registry, _ = _ready_deployments(
        tmp_path
    )

    registry = CustomerLegacyExecutionCompatibilityRegistry(
        tmp_path / "missing.json",
        deployment_registry=deployment_registry,
    )

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        registry.get(
            deployment_id="deployment-001"
        )


def test_record_requires_nonempty_provenance() -> None:
    with pytest.raises(ValueError):
        CustomerLegacyExecutionCompatibilityRecord(
            deployment_id="deployment-001",
            setup_activation_id=" ",
            recovery_request_id=(
                "setup-continuity-recovery:"
                "deployment-001"
            ),
        )



def test_constructor_requires_ready_deployment_registry(
    tmp_path,
) -> None:
    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "deployments.json"
    )

    with pytest.raises(
        ValueError,
        match="deployment_registry must be ready",
    ):
        CustomerLegacyExecutionCompatibilityRegistry(
            tmp_path / "compatibility.json",
            deployment_registry=deployment_registry,
        )


def test_restore_rejects_unknown_deployment_reference(
    tmp_path,
) -> None:
    deployment_registry, _ = _ready_deployments(
        tmp_path
    )

    storage_path = (
        tmp_path / "legacy-execution-compatibility.json"
    )

    storage_path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "deployment_id": "deployment-missing",
                        "setup_activation_id": (
                            "setup-activation-001"
                        ),
                        "recovery_request_id": (
                            "setup-continuity-recovery:"
                            "deployment-missing"
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unknown deployment",
    ):
        CustomerLegacyExecutionCompatibilityRegistry(
            storage_path,
            deployment_registry=deployment_registry,
        )


def test_restore_rejects_duplicate_deployment_records(
    tmp_path,
) -> None:
    deployment_registry, _ = _ready_deployments(
        tmp_path
    )

    storage_path = (
        tmp_path / "legacy-execution-compatibility.json"
    )

    item = {
        "deployment_id": "deployment-001",
        "setup_activation_id": "setup-activation-001",
        "recovery_request_id": (
            "setup-continuity-recovery:deployment-001"
        ),
    }

    storage_path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    item,
                    dict(item),
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate customer legacy execution",
    ):
        CustomerLegacyExecutionCompatibilityRegistry(
            storage_path,
            deployment_registry=deployment_registry,
        )


def test_restore_rejects_unsupported_store_version(
    tmp_path,
) -> None:
    deployment_registry, _ = _ready_deployments(
        tmp_path
    )

    storage_path = (
        tmp_path / "legacy-execution-compatibility.json"
    )

    storage_path.write_text(
        json.dumps(
            {
                "version": 999,
                "records": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported customer legacy execution",
    ):
        CustomerLegacyExecutionCompatibilityRegistry(
            storage_path,
            deployment_registry=deployment_registry,
        )


def test_restore_rejects_invalid_record_schema(
    tmp_path,
) -> None:
    deployment_registry, _ = _ready_deployments(
        tmp_path
    )

    storage_path = (
        tmp_path / "legacy-execution-compatibility.json"
    )

    storage_path.write_text(
        json.dumps(
            {
                "version": 1,
                "records": [
                    {
                        "deployment_id": "deployment-001",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="record has invalid fields",
    ):
        CustomerLegacyExecutionCompatibilityRegistry(
            storage_path,
            deployment_registry=deployment_registry,
        )
