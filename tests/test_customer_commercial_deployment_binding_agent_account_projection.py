import pytest

from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBinding,
    CustomerCommercialDeploymentBindingStore,
)


def _ready_store(tmp_path):
    store = CustomerCommercialDeploymentBindingStore(
        tmp_path / "commercial-deployment-bindings.json"
    )
    store.initialize_empty()
    return store


def _binding(
    *,
    entitlement_id: str,
    customer_id: str,
    deployment_id: str,
    agent_id: str,
    account_fingerprint: str,
):
    return CustomerCommercialDeploymentBinding(
        commercial_entitlement_id=entitlement_id,
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
        account_fingerprint=account_fingerprint,
    )


def test_exact_agent_account_resolves_binding(tmp_path) -> None:
    store = _ready_store(tmp_path)

    expected = _binding(
        entitlement_id="entitlement-001",
        customer_id="customer-001",
        deployment_id="deployment-001",
        agent_id="agent-001",
        account_fingerprint="Broker-Pro:1001",
    )

    store.register(expected)

    store.register(
        _binding(
            entitlement_id="entitlement-002",
            customer_id="customer-002",
            deployment_id="deployment-002",
            agent_id="agent-002",
            account_fingerprint="Broker-Pro:2002",
        )
    )

    result = store.get_by_agent_account(
        agent_id="agent-001",
        account_fingerprint="Broker-Pro:1001",
    )

    assert result == expected


def test_wrong_agent_does_not_resolve(tmp_path) -> None:
    store = _ready_store(tmp_path)

    store.register(
        _binding(
            entitlement_id="entitlement-001",
            customer_id="customer-001",
            deployment_id="deployment-001",
            agent_id="agent-001",
            account_fingerprint="Broker-Pro:1001",
        )
    )

    assert (
        store.get_by_agent_account(
            agent_id="agent-WRONG",
            account_fingerprint="Broker-Pro:1001",
        )
        is None
    )


def test_wrong_account_does_not_resolve(tmp_path) -> None:
    store = _ready_store(tmp_path)

    store.register(
        _binding(
            entitlement_id="entitlement-001",
            customer_id="customer-001",
            deployment_id="deployment-001",
            agent_id="agent-001",
            account_fingerprint="Broker-Pro:1001",
        )
    )

    assert (
        store.get_by_agent_account(
            agent_id="agent-001",
            account_fingerprint="Broker-Pro:WRONG",
        )
        is None
    )


@pytest.mark.parametrize(
    ("agent_id", "account_fingerprint"),
    (
        ("", "Broker-Pro:1001"),
        ("   ", "Broker-Pro:1001"),
        ("agent-001", ""),
        ("agent-001", "   "),
    ),
)
def test_projection_rejects_blank_identity(
    tmp_path,
    agent_id,
    account_fingerprint,
) -> None:
    store = _ready_store(tmp_path)

    with pytest.raises(ValueError):
        store.get_by_agent_account(
            agent_id=agent_id,
            account_fingerprint=account_fingerprint,
        )


def test_projection_fails_closed_when_store_not_ready(
    tmp_path,
) -> None:
    store = CustomerCommercialDeploymentBindingStore(
        tmp_path / "commercial-deployment-bindings.json"
    )

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.get_by_agent_account(
            agent_id="agent-001",
            account_fingerprint="Broker-Pro:1001",
        )
