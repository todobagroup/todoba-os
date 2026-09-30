from pathlib import Path
import ast


MAIN = Path("backend/main.py")


def _source() -> str:
    return MAIN.read_text(
        encoding="utf-8"
    )


def _function_source(
    function_name: str,
) -> str:
    source = _source()
    tree = ast.parse(source)
    lines = source.splitlines()

    matches = [
        node
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        and node.name == function_name
    ]

    assert len(matches) == 1

    node = matches[0]

    return "\n".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


def test_production_composes_one_shared_current_cycle_owner():
    source = _source()

    assert (
        source.count(
            "CustomerCommercialCurrentBillingCycleService("
        )
        == 1
    )

    capacity = _function_source(
        "_compose_customer_commercial_capacity_runtime"
    )

    assert (
        "global "
        "customer_commercial_current_billing_cycle_service"
        in capacity
    )

    assert (
        "customer_commercial_current_billing_cycle_service = ("
        in capacity
    )

    assert (
        "current_billing_cycle_service=(\n"
        "                "
        "customer_commercial_current_billing_cycle_service"
        in capacity
    )


def test_production_initiation_composes_only_existing_authorities():
    composition = _function_source(
        "_compose_customer_vnd_payment_initiation_runtime"
    )

    required = (
        "customer_commercial_current_billing_cycle_service",
        "customer_commercial_vnd_order_pricing_projection_service",
        "customer_commercial_order_service",
        "customer_payment_intent_service",
        "customer_vnd_bank_payment_instruction_service",
        "CustomerVndPaymentInitiationService(",
        "create_customer_vnd_payment_initiation_router(",
        "customer_authentication_dependency=(",
        "app.include_router(",
    )

    for token in required:
        assert token in composition

    forbidden = (
        "CustomerCommercialCurrentBillingCycleStore(",
        "CustomerCommercialBillingCycleBaselineStore(",
        "CustomerCommercialVndOrderPricingProjectionStore(",
        "CustomerCommercialOrderStore(",
        "CustomerPaymentIntentStore(",
        "CustomerVndBankPaymentDestination(",
        "CustomerPaymentSettlementService(",
        "CustomerVndBankReconciliationService(",
        "CustomerSetupActivationService(",
    )

    for token in forbidden:
        assert token not in composition


def test_reconciliation_ingress_exports_existing_order_and_intent_services():
    ingress = _function_source(
        "_compose_authenticated_vnd_reconciliation_ingress"
    )

    assert (
        "global customer_commercial_order_service"
        in ingress
    )

    assert (
        "global customer_payment_intent_service"
        in ingress
    )

    assert (
        ingress.count(
            "CustomerCommercialOrderService("
        )
        == 1
    )

    assert (
        ingress.count(
            "CustomerPaymentIntentService("
        )
        == 1
    )


def test_lifespan_composes_initiation_only_after_all_dependencies():
    lifespan = _function_source(
        "lifespan"
    )

    pricing = lifespan.index(
        "_compose_customer_vnd_pricing_runtime()"
    )

    payment = lifespan.index(
        "_compose_customer_payment_runtime("
    )

    reconciliation = lifespan.index(
        "_compose_authenticated_vnd_reconciliation_ingress("
    )

    capacity = lifespan.index(
        "_compose_customer_commercial_capacity_runtime("
    )

    initiation = lifespan.index(
        "_compose_customer_vnd_payment_initiation_runtime("
    )

    assert (
        pricing
        < payment
        < reconciliation
        < capacity
        < initiation
    )


def test_main_does_not_add_client_monetary_authority():
    composition = _function_source(
        "_compose_customer_vnd_payment_initiation_runtime"
    )

    forbidden = (
        "amount_minor=",
        "currency=",
        "usd_price=",
        "licensed_account_cap_usd=",
        "authoritative_cycle_balance_usd=",
        "bank_code=",
        "account_number=",
        "account_name=",
        "payment_rail=",
    )

    for token in forbidden:
        assert token not in composition


def test_main_does_not_initialize_new_durable_state():
    source = _source()

    assert ".initialize_empty()" not in source
