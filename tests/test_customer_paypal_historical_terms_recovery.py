from decimal import Decimal
from pathlib import Path

import pytest

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineRecord,
)
from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderRecord,
    CustomerCommercialOrderStatus,
)
from backend.commercial.customer_commercial_order_terms_binding import (
    CustomerCommercialOrderTermsBindingRecord,
)
from backend.commercial.customer_payment_settlement_service import (
    CustomerPaymentSettlementRecord,
    CustomerPaymentSettlementStatus,
)


SCRIPT = Path(
    "scripts/customer_paypal_historical_terms_recovery.py"
)


def test_historical_paypal_terms_recovery_owner_exists():
    assert SCRIPT.is_file()


def test_historical_paypal_terms_recovery_is_incident_specific():
    source = SCRIPT.read_text(
        encoding="utf-8-sig"
    )

    required = (
        'SETTLEMENT_ID = "payment-settlement-c7212ef5c542420ca10803b7cbcb32da"',
        'ORDER_ID = "commercial-order-f7320b2d0a0c447a882821d7330492ba"',
        'CUSTOMER_ID = "customer-7fbf874d6bf4413596354c3693ae253a"',
        'CYCLE_ID = "paypal-sandbox-golden-20261006"',
        "licensed_account_cap_usd=4000",
        "standard_monthly_price_usd=140",
    )

    for fragment in required:
        assert fragment in source


def test_historical_paypal_terms_recovery_does_not_gain_payment_truth_authority():
    source = SCRIPT.read_text(
        encoding="utf-8-sig"
    ).lower()

    forbidden = (
        "capture_order(",
        "complete_verified_payment(",
        ".settle(",
        "payment_evidence_service",
        "verification_service",
        "webhook",
    )

    for fragment in forbidden:
        assert fragment not in source


def test_historical_paypal_terms_recovery_uses_authoritative_terms_store_and_activation_bridge():
    source = SCRIPT.read_text(
        encoding="utf-8-sig"
    )

    assert "CustomerCommercialOrderTermsBindingRecord" in source
    assert "order_terms_store.register(" in source
    assert "activate_from_settlement(" in source


def test_historical_paypal_terms_recovery_contract_has_no_caller_supplied_payment_or_pricing_authority():
    import ast

    tree = ast.parse(
        SCRIPT.read_text(
            encoding="utf-8-sig"
        )
    )

    target = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name
            == "recover_historical_paypal_order_terms"
        )
    )

    keyword_names = [
        arg.arg
        for arg in target.args.kwonlyargs
    ]

    assert keyword_names == [
        "settlement_store",
        "order_store",
        "current_billing_cycle_service",
        "order_terms_store",
        "activation_bridge",
    ]


def test_historical_paypal_terms_recovery_hard_guards_precede_terms_mutation():
    source = SCRIPT.read_text(
        encoding="utf-8-sig"
    )

    settlement_index = source.index(
        "settlement = settlement_store.get("
    )
    order_index = source.index(
        "order = order_store.get("
    )
    baseline_index = source.index(
        "current_billing_cycle_service.resolve_current("
    )
    register_index = source.index(
        "order_terms_store.register("
    )
    activate_index = source.index(
        "activation_bridge.activate_from_settlement("
    )

    assert (
        settlement_index
        < order_index
        < baseline_index
        < register_index
        < activate_index
    )
