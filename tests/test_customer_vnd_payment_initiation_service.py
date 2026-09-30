from pathlib import Path


def test_initiation_owner_has_minimal_public_authority() -> None:
    import inspect

    from backend.commercial.customer_vnd_payment_initiation_service import (
        CustomerVndPaymentInitiationService,
    )

    parameters = [
        parameter
        for name, parameter in inspect.signature(
            CustomerVndPaymentInitiationService.initiate
        ).parameters.items()
        if name != "self"
    ]

    assert [
        parameter.name
        for parameter in parameters
    ] == [
        "initiation_request_id",
        "authenticated_customer",
    ]


def test_initiation_owner_contains_no_client_monetary_inputs() -> None:
    import inspect

    from backend.commercial.customer_vnd_payment_initiation_service import (
        CustomerVndPaymentInitiationService,
    )

    signature = inspect.signature(
        CustomerVndPaymentInitiationService.initiate
    )

    forbidden = {
        "customer_id",
        "authoritative_cycle_balance_usd",
        "licensed_account_cap_usd",
        "usd_price",
        "amount_minor",
        "currency",
        "payment_rail",
        "bank_code",
        "account_number",
        "account_name",
        "payment_intent_id",
    }

    assert forbidden.isdisjoint(
        signature.parameters
    )


def test_owner_source_uses_authoritative_chain() -> None:
    source = Path(
        "backend/commercial/customer_vnd_payment_initiation_service.py"
    ).read_text(encoding="utf-8")

    required = (
        ".resolve_current(",
        "baseline.authoritative_cycle_balance_usd",
        "CustomerCommercialAccountPriceBook.quote(",
        "vnd_pricing_projection_service.create(",
        "order_service.create(",
        "payment_intent_service.create(",
        "PaymentRail.VND_BANK_TRANSFER",
        "payment_instruction_service.build(",
    )

    for token in required:
        assert token in source


def test_owner_does_not_expand_settlement_authority() -> None:
    source = Path(
        "backend/commercial/customer_vnd_payment_initiation_service.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "CustomerPaymentSettlementService",
        "CustomerVndBankReconciliationService",
        "CustomerCommercialEntitlementRegistry",
        "CustomerSetupActivationService",
    )

    for token in forbidden:
        assert token not in source
