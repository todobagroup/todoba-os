from pathlib import Path

import pytest

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderService,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementRecord,
    CustomerPaymentSettlementStatus,
    CustomerPaymentSettlementStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationService,
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)
from backend.commercial.customer_payment_settlement_activation_bridge import (
    CustomerPaymentSettlementActivationBridge,
)


def _build(tmp_path: Path):
    identity_registry = CustomerIdentityRegistry(
        tmp_path / "customer-identities.json"
    )
    identity_registry.initialize_empty()

    customer = identity_registry.register(
        CustomerIdentity(
            customer_id="customer-001",
        )
    )

    order_store = CustomerCommercialOrderStore(
        tmp_path / "orders.json"
    )
    order_store.initialize_empty()

    order_service = CustomerCommercialOrderService(
        order_store=order_store,
        customer_identity_registry=identity_registry,
    )

    order = order_service.create(
        order_request_id="order-request-001",
        authorized_customer=customer,
        amount_minor=2500000,
        currency="VND",
    )

    settlement_store = CustomerPaymentSettlementStore(
        tmp_path / "settlements.json"
    )
    settlement_store.initialize_empty()

    settlement = settlement_store.register(
        CustomerPaymentSettlementRecord(
            verification_assertion_id="verification-001",
            settlement_id="payment-settlement-001",
            payment_evidence_id="evidence-001",
            payment_intent_id="payment-intent-001",
            order_id=order.order_id,
            customer_id=order.customer_id,
            amount_minor=order.amount_minor,
            currency=order.currency,
            status=CustomerPaymentSettlementStatus.SETTLED,
        )
    )

    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "deployments.json"
    )
    deployment_registry.initialize_empty()

    activation_store = CustomerSetupActivationStore(
        tmp_path / "activations.json"
    )
    activation_store.initialize_empty()

    activation_service = CustomerSetupActivationService(
        activation_store=activation_store,
        customer_identity_registry=identity_registry,
        deployment_registry=deployment_registry,
    )

    bridge = CustomerPaymentSettlementActivationBridge(
        settlement_store=settlement_store,
        order_store=order_store,
        setup_activation_service=activation_service,
    )

    return (
        bridge,
        settlement,
        order,
        activation_store,
    )


def test_settled_payment_unlocks_setup_activation(
    tmp_path,
):
    (
        bridge,
        settlement,
        order,
        activation_store,
    ) = _build(tmp_path)

    result = bridge.activate_from_settlement(
        settlement_id=settlement.settlement_id,
    )

    assert result.activation_request_id == (
        "payment-settlement-activation-"
        f"{settlement.settlement_id}"
    )
    assert result.customer_id == order.customer_id
    assert (
        result.status
        is CustomerSetupActivationStatus.ACTIVE
    )
    assert activation_store.size() == 1


def test_same_settlement_retry_is_idempotent(
    tmp_path,
):
    (
        bridge,
        settlement,
        _,
        activation_store,
    ) = _build(tmp_path)

    first = bridge.activate_from_settlement(
        settlement_id=settlement.settlement_id,
    )
    second = bridge.activate_from_settlement(
        settlement_id=settlement.settlement_id,
    )

    assert second == first
    assert activation_store.size() == 1


def test_missing_settlement_is_rejected(
    tmp_path,
):
    (
        bridge,
        _,
        _,
        activation_store,
    ) = _build(tmp_path)

    with pytest.raises(ValueError):
        bridge.activate_from_settlement(
            settlement_id="payment-settlement-missing",
        )

    assert activation_store.size() == 0


def test_non_settled_truth_is_rejected(
    tmp_path,
):
    (
        bridge,
        settlement,
        _,
        activation_store,
    ) = _build(tmp_path)

    object.__setattr__(
        settlement,
        "status",
        "PENDING",
    )

    with pytest.raises(ValueError):
        bridge.activate_from_settlement(
            settlement_id=settlement.settlement_id,
        )

    assert activation_store.size() == 0


def test_settlement_customer_must_match_order(
    tmp_path,
):
    (
        bridge,
        settlement,
        _,
        activation_store,
    ) = _build(tmp_path)

    object.__setattr__(
        settlement,
        "customer_id",
        "customer-forged",
    )

    with pytest.raises(ValueError):
        bridge.activate_from_settlement(
            settlement_id=settlement.settlement_id,
        )

    assert activation_store.size() == 0


def test_settlement_amount_must_match_order(
    tmp_path,
):
    (
        bridge,
        settlement,
        _,
        activation_store,
    ) = _build(tmp_path)

    object.__setattr__(
        settlement,
        "amount_minor",
        1,
    )

    with pytest.raises(ValueError):
        bridge.activate_from_settlement(
            settlement_id=settlement.settlement_id,
        )

    assert activation_store.size() == 0


def test_bridge_exposes_no_payment_verification_or_settlement_authority(
    tmp_path,
):
    (
        bridge,
        _,
        _,
        _,
    ) = _build(tmp_path)

    forbidden_methods = (
        "receive",
        "receive_evidence",
        "build_assertion",
        "verify_payment",
        "settle",
        "confirm",
        "mark_paid",
    )

    for method_name in forbidden_methods:
        assert not hasattr(
            bridge,
            method_name,
        )

def test_settlement_order_id_must_match_authoritative_order(
    tmp_path,
):
    (
        bridge,
        settlement,
        _,
        activation_store,
    ) = _build(tmp_path)

    object.__setattr__(
        settlement,
        "order_id",
        "order-forged",
    )

    with pytest.raises(ValueError):
        bridge.activate_from_settlement(
            settlement_id=settlement.settlement_id,
        )

    assert activation_store.size() == 0


def test_settlement_currency_must_match_order(
    tmp_path,
):
    (
        bridge,
        settlement,
        _,
        activation_store,
    ) = _build(tmp_path)

    object.__setattr__(
        settlement,
        "currency",
        "USD",
    )

    with pytest.raises(ValueError):
        bridge.activate_from_settlement(
            settlement_id=settlement.settlement_id,
        )

    assert activation_store.size() == 0


def test_order_status_must_remain_pending(
    tmp_path,
):
    (
        bridge,
        settlement,
        order,
        activation_store,
    ) = _build(tmp_path)

    authoritative_order = (
        bridge._order_store.get(
            order_id=order.order_id
        )
    )
    assert authoritative_order is not None

    object.__setattr__(
        authoritative_order,
        "status",
        "FORGED",
    )

    with pytest.raises(ValueError):
        bridge.activate_from_settlement(
            settlement_id=settlement.settlement_id,
        )

    assert activation_store.size() == 0


def test_retry_never_reactivates_suspended_activation(
    tmp_path,
):
    (
        bridge,
        settlement,
        _,
        activation_store,
    ) = _build(tmp_path)

    first = bridge.activate_from_settlement(
        settlement_id=settlement.settlement_id,
    )

    suspended = activation_store.suspend(
        setup_activation_id=first.setup_activation_id,
    )

    assert (
        suspended.status
        is CustomerSetupActivationStatus.SUSPENDED
    )

    retried = bridge.activate_from_settlement(
        settlement_id=settlement.settlement_id,
    )

    assert retried.setup_activation_id == first.setup_activation_id
    assert (
        retried.status
        is CustomerSetupActivationStatus.SUSPENDED
    )
    assert activation_store.size() == 1


def test_bridge_has_no_direct_activation_store_write_authority(
    tmp_path,
):
    (
        bridge,
        _,
        _,
        _,
    ) = _build(tmp_path)

    forbidden_methods = (
        "register",
        "save",
        "persist",
        "suspend",
        "reactivate",
        "bind",
    )

    for method_name in forbidden_methods:
        assert not hasattr(
            bridge,
            method_name,
        )
