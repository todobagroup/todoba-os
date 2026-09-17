from __future__ import annotations

from pathlib import Path

import pytest

from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBinding,
    CustomerCommercialDeploymentBindingStore,
)


def _store(
    tmp_path: Path,
) -> CustomerCommercialDeploymentBindingStore:
    store = CustomerCommercialDeploymentBindingStore(
        tmp_path / "commercial_deployment_bindings.json"
    )
    store.initialize_empty()
    return store


def _binding(
    *,
    commercial_entitlement_id: str = "commercial-entitlement-001",
    customer_id: str = "customer-001",
    deployment_id: str = "deployment-001",
    agent_id: str = "trusted-agent-001",
    account_fingerprint: str = "RoboForex-Pro:68353796",
) -> CustomerCommercialDeploymentBinding:
    return CustomerCommercialDeploymentBinding(
        commercial_entitlement_id=commercial_entitlement_id,
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
        account_fingerprint=account_fingerprint,
    )


def test_binding_surface_is_exact_and_narrow():
    assert set(
        CustomerCommercialDeploymentBinding.__dataclass_fields__
    ) == {
        "commercial_entitlement_id",
        "customer_id",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
    }


def test_registers_exact_commercial_deployment_binding(
    tmp_path: Path,
):
    store = _store(tmp_path)

    binding = _binding()

    result = store.register(
        binding
    )

    assert result == binding

    assert (
        store.get_by_entitlement_id(
            commercial_entitlement_id=(
                "commercial-entitlement-001"
            )
        )
        == binding
    )

    assert (
        store.get_by_deployment_id(
            deployment_id="deployment-001"
        )
        == binding
    )


def test_identical_retry_is_idempotent(
    tmp_path: Path,
):
    store = _store(tmp_path)

    first = _binding()
    second = _binding()

    assert store.register(first) == first
    assert store.register(second) == first
    assert store.size() == 1


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("customer_id", "customer-other"),
        ("deployment_id", "deployment-other"),
        ("agent_id", "trusted-agent-other"),
        (
            "account_fingerprint",
            "Other-Broker:99999999",
        ),
    ),
)
def test_entitlement_cannot_be_rebound_to_other_deployment_truth(
    tmp_path: Path,
    field: str,
    value: str,
):
    store = _store(tmp_path)

    original = _binding()
    store.register(original)

    kwargs = {
        "commercial_entitlement_id": (
            "commercial-entitlement-001"
        ),
        "customer_id": "customer-001",
        "deployment_id": "deployment-001",
        "agent_id": "trusted-agent-001",
        "account_fingerprint": (
            "RoboForex-Pro:68353796"
        ),
    }
    kwargs[field] = value

    with pytest.raises(
        ValueError,
        match="entitlement",
    ):
        store.register(
            CustomerCommercialDeploymentBinding(
                **kwargs
            )
        )

    assert store.size() == 1
    assert (
        store.get_by_entitlement_id(
            commercial_entitlement_id=(
                "commercial-entitlement-001"
            )
        )
        == original
    )


def test_deployment_cannot_consume_two_commercial_entitlements(
    tmp_path: Path,
):
    store = _store(tmp_path)

    store.register(
        _binding()
    )

    with pytest.raises(
        ValueError,
        match="deployment",
    ):
        store.register(
            _binding(
                commercial_entitlement_id=(
                    "commercial-entitlement-002"
                )
            )
        )

    assert store.size() == 1


def test_different_entitlements_can_bind_independent_deployments(
    tmp_path: Path,
):
    store = _store(tmp_path)

    first = store.register(
        _binding()
    )

    second = store.register(
        _binding(
            commercial_entitlement_id=(
                "commercial-entitlement-002"
            ),
            deployment_id="deployment-002",
            agent_id="trusted-agent-002",
            account_fingerprint=(
                "RoboForex-Pro:68353797"
            ),
        )
    )

    assert first != second
    assert store.size() == 2


def test_missing_lookups_return_none(
    tmp_path: Path,
):
    store = _store(tmp_path)

    assert (
        store.get_by_entitlement_id(
            commercial_entitlement_id="missing"
        )
        is None
    )

    assert (
        store.get_by_deployment_id(
            deployment_id="missing"
        )
        is None
    )


def test_binding_survives_restart(
    tmp_path: Path,
):
    path = (
        tmp_path
        / "commercial_deployment_bindings.json"
    )

    store = CustomerCommercialDeploymentBindingStore(
        path
    )
    store.initialize_empty()

    created = store.register(
        _binding()
    )

    restored = CustomerCommercialDeploymentBindingStore(
        path
    )

    assert restored.is_ready()

    assert (
        restored.get_by_entitlement_id(
            commercial_entitlement_id=(
                created.commercial_entitlement_id
            )
        )
        == created
    )

    assert (
        restored.get_by_deployment_id(
            deployment_id=created.deployment_id
        )
        == created
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("commercial_entitlement_id", ""),
        ("customer_id", ""),
        ("deployment_id", ""),
        ("agent_id", ""),
        ("account_fingerprint", ""),
    ),
)
def test_empty_identity_fails_closed(
    field: str,
    value: str,
):
    kwargs = {
        "commercial_entitlement_id": (
            "commercial-entitlement-001"
        ),
        "customer_id": "customer-001",
        "deployment_id": "deployment-001",
        "agent_id": "trusted-agent-001",
        "account_fingerprint": (
            "RoboForex-Pro:68353796"
        ),
    }
    kwargs[field] = value

    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerCommercialDeploymentBinding(
            **kwargs
        )


def test_binding_has_no_cap_price_payment_setup_or_runtime_authority():
    fields = set(
        CustomerCommercialDeploymentBinding.__dataclass_fields__
    )

    forbidden_fields = {
        "licensed_account_cap_usd",
        "standard_monthly_price_usd",
        "amount_minor",
        "currency",
        "setup_activation_id",
        "status",
    }

    assert fields.isdisjoint(
        forbidden_fields
    )

    forbidden_methods = {
        "settle",
        "activate_setup",
        "activate_deployment_entitlement",
        "authorize_runtime",
        "bind_account",
    }

    assert forbidden_methods.isdisjoint(
        set(
            dir(
                CustomerCommercialDeploymentBindingStore
            )
        )
    )
