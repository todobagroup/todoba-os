"""
TODOBA Customer Deployment Entitlement Registry Tests

Durability and security proof:
- entitlement identity is deployment_id
- no record means no entitlement
- ACTIVE grants entitlement truth
- SUSPENDED removes active entitlement without destroying identity
- SUSPENDED may be activated again
- one customer may have independently entitled deployments
- different customers remain isolated
- unknown deployments cannot receive entitlement
- missing entitlement cannot be suspended
- activate/suspend are idempotent when already in target state
- persistence survives restart
- corrupt, duplicate, invalid-status, and orphaned durable truth
  fail closed
- durable write failure never advances in-memory entitlement truth
- persisted entitlement records contain no customer_id, agent_id,
  payment, credential, secret, or package data

All durable state is isolated beneath pytest tmp_path.
"""

from inspect import signature
import json
from pathlib import Path

import pytest

from backend.commercial.customer_deployment_entitlement_registry import (
    STORE_VERSION,
    CustomerDeploymentEntitlement,
    CustomerDeploymentEntitlementRegistry,
    CustomerDeploymentEntitlementStatus,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)


def build_deployment_registry(
    tmp_path: Path,
) -> tuple[
    CustomerDeploymentRegistry,
    CustomerDeployment,
    CustomerDeployment,
    CustomerDeployment,
]:
    registry = CustomerDeploymentRegistry(
        tmp_path
        / "customer_deployments.json"
    )

    registry.initialize_empty()

    deployment_a = CustomerDeployment(
        customer_id="customer-d4-a",
        deployment_id="deployment-d4-a",
        agent_id="agent-d4-a",
    )

    deployment_a_second = CustomerDeployment(
        customer_id="customer-d4-a",
        deployment_id="deployment-d4-a-second",
        agent_id="agent-d4-a-second",
    )

    deployment_b = CustomerDeployment(
        customer_id="customer-d4-b",
        deployment_id="deployment-d4-b",
        agent_id="agent-d4-b",
    )

    registry.register(deployment_a)
    registry.register(deployment_a_second)
    registry.register(deployment_b)

    return (
        registry,
        deployment_a,
        deployment_a_second,
        deployment_b,
    )


def build_entitlement_registry(
    tmp_path: Path,
) -> tuple[
    CustomerDeploymentEntitlementRegistry,
    CustomerDeploymentRegistry,
    CustomerDeployment,
    CustomerDeployment,
    CustomerDeployment,
]:
    (
        deployments,
        deployment_a,
        deployment_a_second,
        deployment_b,
    ) = build_deployment_registry(
        tmp_path
    )

    entitlements = (
        CustomerDeploymentEntitlementRegistry(
            tmp_path
            / "customer_deployment_entitlements.json",
            deployment_registry=deployments,
        )
    )

    entitlements.initialize_empty()

    return (
        entitlements,
        deployments,
        deployment_a,
        deployment_a_second,
        deployment_b,
    )


def test_entitlement_record_normalizes_deployment_id() -> None:
    record = CustomerDeploymentEntitlement(
        deployment_id="  deployment-d4-a  ",
        status=(
            CustomerDeploymentEntitlementStatus.ACTIVE
        ),
    )

    assert record.deployment_id == "deployment-d4-a"


@pytest.mark.parametrize(
    "deployment_id",
    (
        "",
        "   ",
        None,
        123,
        object(),
    ),
)
def test_entitlement_record_rejects_invalid_deployment_id(
    deployment_id,
) -> None:
    with pytest.raises(
        (
            TypeError,
            ValueError,
        )
    ):
        CustomerDeploymentEntitlement(
            deployment_id=deployment_id,
            status=(
                CustomerDeploymentEntitlementStatus.ACTIVE
            ),
        )


def test_entitlement_record_requires_status_enum() -> None:
    with pytest.raises(
        TypeError,
        match="CustomerDeploymentEntitlementStatus",
    ):
        CustomerDeploymentEntitlement(
            deployment_id="deployment-d4-a",
            status="ACTIVE",
        )


def test_constructor_requires_path(
    tmp_path: Path,
) -> None:
    (
        deployments,
        _,
        _,
        _,
    ) = build_deployment_registry(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="storage_path",
    ):
        CustomerDeploymentEntitlementRegistry(
            "not-a-path",
            deployment_registry=deployments,
        )


def test_constructor_requires_deployment_registry(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="CustomerDeploymentRegistry",
    ):
        CustomerDeploymentEntitlementRegistry(
            tmp_path
            / "customer_deployment_entitlements.json",
            deployment_registry=object(),
        )


def test_constructor_requires_ready_deployment_registry(
    tmp_path: Path,
) -> None:
    deployments = CustomerDeploymentRegistry(
        tmp_path
        / "customer_deployments.json"
    )

    assert deployments.is_ready() is False

    with pytest.raises(
        ValueError,
        match="ready",
    ):
        CustomerDeploymentEntitlementRegistry(
            tmp_path
            / "customer_deployment_entitlements.json",
            deployment_registry=deployments,
        )


def test_registry_requires_initialization_before_reads(
    tmp_path: Path,
) -> None:
    (
        deployments,
        deployment_a,
        _,
        _,
    ) = build_deployment_registry(
        tmp_path
    )

    registry = CustomerDeploymentEntitlementRegistry(
        tmp_path
        / "customer_deployment_entitlements.json",
        deployment_registry=deployments,
    )

    assert registry.is_ready() is False

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        registry.get(
            deployment_id=deployment_a.deployment_id
        )


def test_initialize_empty_creates_durable_empty_truth(
    tmp_path: Path,
) -> None:
    (
        deployments,
        _,
        _,
        _,
    ) = build_deployment_registry(
        tmp_path
    )

    storage_path = (
        tmp_path
        / "customer_deployment_entitlements.json"
    )

    registry = CustomerDeploymentEntitlementRegistry(
        storage_path,
        deployment_registry=deployments,
    )

    registry.initialize_empty()

    assert registry.is_ready() is True
    assert registry.size() == 0
    assert registry.all() == ()

    payload = json.loads(
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert payload == {
        "entitlements": [],
        "version": STORE_VERSION,
    }


def test_initialize_empty_is_not_repeatable(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        _,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="already ready",
    ):
        registry.initialize_empty()


def test_activate_and_suspend_signatures_accept_only_deployment_id(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        _,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    assert tuple(
        signature(
            registry.activate
        ).parameters
    ) == (
        "deployment_id",
    )

    assert tuple(
        signature(
            registry.suspend
        ).parameters
    ) == (
        "deployment_id",
    )


def test_no_record_means_no_entitlement(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    assert (
        registry.get(
            deployment_id=deployment_a.deployment_id
        )
        is None
    )

    assert (
        registry.is_active(
            deployment_id=deployment_a.deployment_id
        )
        is False
    )


def test_activate_creates_active_entitlement(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    result = registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    assert (
        result.status
        is CustomerDeploymentEntitlementStatus.ACTIVE
    )

    assert (
        result.deployment_id
        == deployment_a.deployment_id
    )

    assert (
        registry.is_active(
            deployment_id=deployment_a.deployment_id
        )
        is True
    )


def test_activate_is_idempotent(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    first = registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    before = registry.storage_path.read_bytes()

    second = registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    assert second is first
    assert registry.storage_path.read_bytes() == before
    assert registry.size() == 1


def test_suspend_active_entitlement(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    result = registry.suspend(
        deployment_id=deployment_a.deployment_id
    )

    assert (
        result.status
        is CustomerDeploymentEntitlementStatus.SUSPENDED
    )

    assert (
        registry.is_active(
            deployment_id=deployment_a.deployment_id
        )
        is False
    )


def test_suspend_is_idempotent(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    first = registry.suspend(
        deployment_id=deployment_a.deployment_id
    )

    before = registry.storage_path.read_bytes()

    second = registry.suspend(
        deployment_id=deployment_a.deployment_id
    )

    assert second is first
    assert registry.storage_path.read_bytes() == before


def test_suspended_entitlement_can_be_reactivated(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    registry.suspend(
        deployment_id=deployment_a.deployment_id
    )

    result = registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    assert (
        result.status
        is CustomerDeploymentEntitlementStatus.ACTIVE
    )

    assert (
        registry.is_active(
            deployment_id=deployment_a.deployment_id
        )
        is True
    )


def test_same_customer_deployments_are_independent(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        deployment_a_second,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    assert (
        registry.is_active(
            deployment_id=deployment_a.deployment_id
        )
        is True
    )

    assert (
        registry.is_active(
            deployment_id=(
                deployment_a_second.deployment_id
            )
        )
        is False
    )

    registry.activate(
        deployment_id=(
            deployment_a_second.deployment_id
        )
    )

    registry.suspend(
        deployment_id=deployment_a.deployment_id
    )

    assert (
        registry.is_active(
            deployment_id=deployment_a.deployment_id
        )
        is False
    )

    assert (
        registry.is_active(
            deployment_id=(
                deployment_a_second.deployment_id
            )
        )
        is True
    )


def test_different_customer_deployments_are_independent(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        deployment_b,
    ) = build_entitlement_registry(
        tmp_path
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    assert (
        registry.is_active(
            deployment_id=deployment_b.deployment_id
        )
        is False
    )


def test_unknown_deployment_cannot_be_activated(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        _,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    before = registry.storage_path.read_bytes()
    before_size = registry.size()

    with pytest.raises(
        ValueError,
        match="does not exist",
    ):
        registry.activate(
            deployment_id="deployment-unknown"
        )

    assert registry.size() == before_size
    assert registry.storage_path.read_bytes() == before


def test_missing_entitlement_cannot_be_suspended(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    before = registry.storage_path.read_bytes()

    with pytest.raises(
        ValueError,
        match="does not exist",
    ):
        registry.suspend(
            deployment_id=deployment_a.deployment_id
        )

    assert registry.size() == 0
    assert registry.storage_path.read_bytes() == before


@pytest.mark.parametrize(
    "deployment_id",
    (
        "",
        "   ",
        None,
        123,
        object(),
    ),
)
def test_is_active_fails_closed_for_malformed_deployment_id(
    tmp_path: Path,
    deployment_id,
) -> None:
    (
        registry,
        _,
        _,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    assert (
        registry.is_active(
            deployment_id=deployment_id
        )
        is False
    )


def test_persisted_record_contains_only_deployment_and_status(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    payload = json.loads(
        registry.storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert set(payload) == {
        "version",
        "entitlements",
    }

    assert len(
        payload["entitlements"]
    ) == 1

    item = payload[
        "entitlements"
    ][0]

    assert set(item) == {
        "deployment_id",
        "status",
    }

    persisted_text = registry.storage_path.read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "customer_id",
        "agent_id",
        "payment_id",
        "subscription_id",
        "access_credential",
        "secret",
        "package_path",
    ):
        assert forbidden not in persisted_text


def test_active_and_suspended_states_survive_restart(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployments,
        deployment_a,
        deployment_a_second,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    registry.activate(
        deployment_id=(
            deployment_a_second.deployment_id
        )
    )

    registry.suspend(
        deployment_id=deployment_a.deployment_id
    )

    restarted = CustomerDeploymentEntitlementRegistry(
        registry.storage_path,
        deployment_registry=deployments,
    )

    assert restarted.is_ready() is True
    assert restarted.size() == 2

    assert (
        restarted.get(
            deployment_id=deployment_a.deployment_id
        ).status
        is CustomerDeploymentEntitlementStatus.SUSPENDED
    )

    assert (
        restarted.get(
            deployment_id=(
                deployment_a_second.deployment_id
            )
        ).status
        is CustomerDeploymentEntitlementStatus.ACTIVE
    )


def test_reactivation_survives_restart(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployments,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    registry.suspend(
        deployment_id=deployment_a.deployment_id
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    restarted = CustomerDeploymentEntitlementRegistry(
        registry.storage_path,
        deployment_registry=deployments,
    )

    assert (
        restarted.is_active(
            deployment_id=deployment_a.deployment_id
        )
        is True
    )


def test_all_is_deterministic_by_deployment_id(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        deployment_a,
        deployment_a_second,
        deployment_b,
    ) = build_entitlement_registry(
        tmp_path
    )

    registry.activate(
        deployment_id=deployment_b.deployment_id
    )

    registry.activate(
        deployment_id=deployment_a_second.deployment_id
    )

    registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    assert tuple(
        item.deployment_id
        for item in registry.all()
    ) == tuple(
        sorted(
            (
                deployment_a.deployment_id,
                deployment_a_second.deployment_id,
                deployment_b.deployment_id,
            )
        )
    )


def test_activate_write_failure_does_not_advance_ram_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    before_disk = registry.storage_path.read_bytes()
    before_size = registry.size()

    def fail_write(
        _candidate,
    ) -> None:
        raise OSError(
            "simulated entitlement write failure"
        )

    monkeypatch.setattr(
        registry,
        "_write_entitlements",
        fail_write,
    )

    with pytest.raises(
        OSError,
        match="simulated entitlement write failure",
    ):
        registry.activate(
            deployment_id=deployment_a.deployment_id
        )

    assert registry.size() == before_size

    assert (
        registry.get(
            deployment_id=deployment_a.deployment_id
        )
        is None
    )

    assert registry.storage_path.read_bytes() == before_disk


def test_suspend_write_failure_preserves_active_ram_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        registry,
        _,
        deployment_a,
        _,
        _,
    ) = build_entitlement_registry(
        tmp_path
    )

    active = registry.activate(
        deployment_id=deployment_a.deployment_id
    )

    before_disk = registry.storage_path.read_bytes()
    before_size = registry.size()

    def fail_write(
        _candidate,
    ) -> None:
        raise OSError(
            "simulated entitlement write failure"
        )

    monkeypatch.setattr(
        registry,
        "_write_entitlements",
        fail_write,
    )

    with pytest.raises(
        OSError,
        match="simulated entitlement write failure",
    ):
        registry.suspend(
            deployment_id=deployment_a.deployment_id
        )

    assert registry.size() == before_size

    assert (
        registry.get(
            deployment_id=deployment_a.deployment_id
        )
        is active
    )

    assert (
        registry.is_active(
            deployment_id=deployment_a.deployment_id
        )
        is True
    )

    assert registry.storage_path.read_bytes() == before_disk


def write_entitlement_payload(
    path: Path,
    payload,
) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_restore_rejects_corrupt_json(
    tmp_path: Path,
) -> None:
    (
        deployments,
        _,
        _,
        _,
    ) = build_deployment_registry(
        tmp_path
    )

    storage_path = (
        tmp_path
        / "customer_deployment_entitlements.json"
    )

    storage_path.write_text(
        "{not-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unreadable",
    ):
        CustomerDeploymentEntitlementRegistry(
            storage_path,
            deployment_registry=deployments,
        )


def test_restore_rejects_wrong_store_version(
    tmp_path: Path,
) -> None:
    (
        deployments,
        _,
        _,
        _,
    ) = build_deployment_registry(
        tmp_path
    )

    storage_path = (
        tmp_path
        / "customer_deployment_entitlements.json"
    )

    write_entitlement_payload(
        storage_path,
        {
            "version": STORE_VERSION + 1,
            "entitlements": [],
        },
    )

    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        CustomerDeploymentEntitlementRegistry(
            storage_path,
            deployment_registry=deployments,
        )


def test_restore_rejects_duplicate_entitlement(
    tmp_path: Path,
) -> None:
    (
        deployments,
        deployment_a,
        _,
        _,
    ) = build_deployment_registry(
        tmp_path
    )

    storage_path = (
        tmp_path
        / "customer_deployment_entitlements.json"
    )

    item = {
        "deployment_id": deployment_a.deployment_id,
        "status": "ACTIVE",
    }

    write_entitlement_payload(
        storage_path,
        {
            "version": STORE_VERSION,
            "entitlements": [
                item,
                dict(item),
            ],
        },
    )

    with pytest.raises(
        ValueError,
        match="Duplicate",
    ):
        CustomerDeploymentEntitlementRegistry(
            storage_path,
            deployment_registry=deployments,
        )


def test_restore_rejects_orphaned_entitlement(
    tmp_path: Path,
) -> None:
    (
        deployments,
        _,
        _,
        _,
    ) = build_deployment_registry(
        tmp_path
    )

    storage_path = (
        tmp_path
        / "customer_deployment_entitlements.json"
    )

    write_entitlement_payload(
        storage_path,
        {
            "version": STORE_VERSION,
            "entitlements": [
                {
                    "deployment_id": (
                        "deployment-not-registered"
                    ),
                    "status": "ACTIVE",
                }
            ],
        },
    )

    with pytest.raises(
        ValueError,
        match="unknown deployment",
    ):
        CustomerDeploymentEntitlementRegistry(
            storage_path,
            deployment_registry=deployments,
        )


def test_restore_rejects_invalid_status(
    tmp_path: Path,
) -> None:
    (
        deployments,
        deployment_a,
        _,
        _,
    ) = build_deployment_registry(
        tmp_path
    )

    storage_path = (
        tmp_path
        / "customer_deployment_entitlements.json"
    )

    write_entitlement_payload(
        storage_path,
        {
            "version": STORE_VERSION,
            "entitlements": [
                {
                    "deployment_id": (
                        deployment_a.deployment_id
                    ),
                    "status": "REVOKED",
                }
            ],
        },
    )

    with pytest.raises(
        ValueError,
        match="invalid",
    ):
        CustomerDeploymentEntitlementRegistry(
            storage_path,
            deployment_registry=deployments,
        )


def test_restore_rejects_unexpected_record_fields(
    tmp_path: Path,
) -> None:
    (
        deployments,
        deployment_a,
        _,
        _,
    ) = build_deployment_registry(
        tmp_path
    )

    storage_path = (
        tmp_path
        / "customer_deployment_entitlements.json"
    )

    write_entitlement_payload(
        storage_path,
        {
            "version": STORE_VERSION,
            "entitlements": [
                {
                    "deployment_id": (
                        deployment_a.deployment_id
                    ),
                    "status": "ACTIVE",
                    "customer_id": "forged-customer",
                }
            ],
        },
    )

    with pytest.raises(
        ValueError,
        match="invalid fields",
    ):
        CustomerDeploymentEntitlementRegistry(
            storage_path,
            deployment_registry=deployments,
        )
