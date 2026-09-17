from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlement,
    CustomerCommercialEntitlementStatus,
)
from backend.commercial.customer_payment_settlement_activation_bridge import (
    CustomerPaymentSettlementActivationBridge,
)


class _FakeEntitlementConvergenceService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def converge(
        self,
        *,
        settlement_id: str,
    ) -> CustomerCommercialEntitlement:
        self.calls.append(
            settlement_id
        )

        return CustomerCommercialEntitlement(
            entitlement_id=(
                "commercial-entitlement-"
                f"{settlement_id}"
            ),
            order_id="order-001",
            customer_id="customer-001",
            licensed_account_cap_usd=1000,
            standard_monthly_price_usd=50,
            status=(
                CustomerCommercialEntitlementStatus.ACTIVE
            ),
        )


class _FakeSetupActivationService:
    def __init__(self) -> None:
        self.calls = []

    def activate(
        self,
        *,
        activation_request_id: str,
        customer_id: str,
    ):
        self.calls.append(
            (
                activation_request_id,
                customer_id,
            )
        )

        return object()


def test_bridge_constructor_requires_entitlement_gate_not_raw_payment_stores():
    signature = inspect.signature(
        CustomerPaymentSettlementActivationBridge
    )

    assert tuple(
        signature.parameters
    ) == (
        "entitlement_convergence_service",
        "setup_activation_service",
    )


def test_bridge_converges_entitlement_before_setup_activation():
    entitlement_service = (
        _FakeEntitlementConvergenceService()
    )
    setup_service = (
        _FakeSetupActivationService()
    )

    bridge = CustomerPaymentSettlementActivationBridge(
        entitlement_convergence_service=(
            entitlement_service
        ),
        setup_activation_service=setup_service,
    )

    result = bridge.activate_from_settlement(
        settlement_id="payment-settlement-001"
    )

    assert result is not None

    assert entitlement_service.calls == [
        "payment-settlement-001"
    ]

    assert setup_service.calls == [
        (
            (
                "payment-settlement-activation-"
                "payment-settlement-001"
            ),
            "customer-001",
        )
    ]


def test_bridge_rejects_non_active_entitlement_before_setup_activation():
    class SuspendedConvergenceService(
        _FakeEntitlementConvergenceService
    ):
        def converge(
            self,
            *,
            settlement_id: str,
        ):
            self.calls.append(
                settlement_id
            )

            return CustomerCommercialEntitlement(
                entitlement_id=(
                    "commercial-entitlement-"
                    f"{settlement_id}"
                ),
                order_id="order-001",
                customer_id="customer-001",
                licensed_account_cap_usd=1000,
                standard_monthly_price_usd=50,
                status=(
                    CustomerCommercialEntitlementStatus.SUSPENDED
                ),
            )

    entitlement_service = SuspendedConvergenceService()
    setup_service = _FakeSetupActivationService()

    bridge = CustomerPaymentSettlementActivationBridge(
        entitlement_convergence_service=(
            entitlement_service
        ),
        setup_activation_service=setup_service,
    )

    with pytest.raises(
        ValueError,
        match="ACTIVE commercial entitlement",
    ):
        bridge.activate_from_settlement(
            settlement_id="payment-settlement-001"
        )

    assert setup_service.calls == []


def test_bridge_rejects_wrong_entitlement_identity_before_setup_activation():
    class WrongIdentityConvergenceService(
        _FakeEntitlementConvergenceService
    ):
        def converge(
            self,
            *,
            settlement_id: str,
        ):
            self.calls.append(
                settlement_id
            )

            return CustomerCommercialEntitlement(
                entitlement_id="commercial-entitlement-other",
                order_id="order-001",
                customer_id="customer-001",
                licensed_account_cap_usd=1000,
                standard_monthly_price_usd=50,
                status=(
                    CustomerCommercialEntitlementStatus.ACTIVE
                ),
            )

    entitlement_service = WrongIdentityConvergenceService()
    setup_service = _FakeSetupActivationService()

    bridge = CustomerPaymentSettlementActivationBridge(
        entitlement_convergence_service=(
            entitlement_service
        ),
        setup_activation_service=setup_service,
    )

    with pytest.raises(
        RuntimeError,
        match="entitlement identity",
    ):
        bridge.activate_from_settlement(
            settlement_id="payment-settlement-001"
        )

    assert setup_service.calls == []


def test_bridge_source_has_no_raw_settlement_or_order_store_authority():
    path = Path(
        "backend/commercial/"
        "customer_payment_settlement_activation_bridge.py"
    )

    text = path.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )

    tree = ast.parse(
        text,
        filename=str(path),
    )

    bridge = next(
        node
        for node in tree.body
        if isinstance(
            node,
            ast.ClassDef,
        )
        and node.name
        == "CustomerPaymentSettlementActivationBridge"
    )

    init = next(
        node
        for node in bridge.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name == "__init__"
    )

    init_source = ast.get_source_segment(
        text,
        init,
    )

    assert "settlement_store" not in init_source
    assert "order_store" not in init_source

    activate = next(
        node
        for node in bridge.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name == "activate_from_settlement"
    )

    source = ast.get_source_segment(
        text,
        activate,
    )

    assert ".converge(" in source
    assert "_settlement_store" not in source
    assert "_order_store" not in source


def test_main_defines_p9d3_durable_paths_and_owners():
    path = Path("backend/main.py")

    text = path.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )

    for required in (
        "CUSTOMER_COMMERCIAL_ORDER_TERMS_BINDING_STORAGE_PATH",
        "CUSTOMER_COMMERCIAL_ENTITLEMENT_STORAGE_PATH",
        "CustomerCommercialOrderTermsBindingStore",
        "CustomerCommercialEntitlementRegistry",
        "CustomerPaymentSettlementEntitlementConvergenceService",
    ):
        assert required in text


def test_payment_runtime_composes_entitlement_gate_before_activation_bridge():
    path = Path("backend/main.py")

    text = path.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )

    tree = ast.parse(
        text,
        filename=str(path),
    )

    compose = next(
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name
        == "_compose_customer_payment_runtime"
    )

    source = ast.get_source_segment(
        text,
        compose,
    )

    convergence_index = source.index(
        "CustomerPaymentSettlementEntitlementConvergenceService("
    )

    bridge_index = source.index(
        "CustomerPaymentSettlementActivationBridge("
    )

    assert convergence_index < bridge_index

    assert (
        "entitlement_convergence_service="
        in source
    )


def test_payment_runtime_requires_eight_durable_stores():
    path = Path(
        "tests/test_customer_payment_production_composition.py"
    )

    text = path.read_text(
        encoding="utf-8-sig"
    ).replace(
        "\r\n",
        "\n",
    )

    assert (
        "test_payment_runtime_owns_exact_eight_durable_stores"
        in text
    )

    assert (
        "CUSTOMER_COMMERCIAL_ORDER_TERMS_BINDING_STORAGE_PATH"
        in text
    )

    assert (
        "CUSTOMER_COMMERCIAL_ENTITLEMENT_STORAGE_PATH"
        in text
    )
