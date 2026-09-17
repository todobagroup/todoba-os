"""
P9A2 — Commercial Account Tier / USD Price Book Authority

Pricing boundary:

authoritative account balance captured at cycle start / renewal
->
licensed account cap USD
->
standard monthly price USD

Important separation:

This Price Book does NOT observe live account balance.

It does NOT decide whether an in-cycle balance increase came from:
- trading profit
- trading loss
- external deposit
- external withdrawal

It does NOT own:
- billing-cycle baseline persistence
- external funding observation
- runtime grace
- upgrade enforcement
- downgrade timing
- FX
- payment
- order creation
- promotions
- entitlement

Those are separate commercial capabilities.
"""

from decimal import Decimal

import pytest

from backend.commercial.customer_commercial_account_price_book import (
    CustomerCommercialAccountPriceBook,
    CustomerCommercialAccountPriceQuote,
    CustomerCommercialAccountPricingUnavailable,
)


def quote(
    cycle_balance: str,
) -> CustomerCommercialAccountPriceQuote:
    return CustomerCommercialAccountPriceBook.quote(
        authoritative_cycle_balance_usd=Decimal(
            cycle_balance
        )
    )


@pytest.mark.parametrize(
    (
        "cycle_balance",
        "expected_cap",
        "expected_price",
    ),
    [
        ("100.00", 1000, 50),
        ("999.99", 1000, 50),
        ("1000.00", 1000, 50),
        ("1000.01", 2000, 80),
        ("1200.00", 2000, 80),
        ("2000.00", 2000, 80),
        ("2000.01", 3000, 110),
        ("3000.00", 3000, 110),
        ("4000.00", 4000, 140),
        ("5000.00", 5000, 170),
        ("6000.00", 6000, 190),
        ("7000.00", 7000, 210),
        ("7000.01", 8000, 230),
        ("7300.00", 8000, 230),
        ("8000.00", 8000, 230),
        ("9000.00", 9000, 250),
        ("10000.00", 10000, 270),
        ("10000.01", 11000, 282),
        ("11000.00", 11000, 282),
        ("12000.00", 12000, 294),
        ("25000.00", 25000, 450),
        ("25000.01", 26000, 458),
        ("26000.00", 26000, 458),
        ("27000.00", 27000, 466),
        ("50000.00", 50000, 650),
    ],
)
def test_cycle_boundary_balance_maps_to_standard_tier(
    cycle_balance: str,
    expected_cap: int,
    expected_price: int,
) -> None:
    result = quote(
        cycle_balance
    )

    assert isinstance(
        result,
        CustomerCommercialAccountPriceQuote,
    )

    assert (
        result.licensed_account_cap_usd
        == expected_cap
    )

    assert (
        result.standard_monthly_price_usd
        == expected_price
    )


def test_cycle_boundary_uses_exact_decimal_tier_boundary():
    at_cap = quote("7000.00")
    above_cap = quote("7000.01")

    assert (
        at_cap.licensed_account_cap_usd
        == 7000
    )
    assert (
        at_cap.standard_monthly_price_usd
        == 210
    )

    assert (
        above_cap.licensed_account_cap_usd
        == 8000
    )
    assert (
        above_cap.standard_monthly_price_usd
        == 230
    )


def test_renewal_reprices_from_new_cycle_balance():
    previous_cycle = quote("1000.00")
    renewed_cycle = quote("1200.00")

    assert (
        previous_cycle.licensed_account_cap_usd
        == 1000
    )
    assert (
        previous_cycle.standard_monthly_price_usd
        == 50
    )

    assert (
        renewed_cycle.licensed_account_cap_usd
        == 2000
    )
    assert (
        renewed_cycle.standard_monthly_price_usd
        == 80
    )


def test_price_book_rejects_balance_below_supported_minimum():
    with pytest.raises(
        CustomerCommercialAccountPricingUnavailable,
        match="below supported minimum",
    ):
        quote("99.99")


def test_price_book_requires_custom_pricing_above_automatic_limit():
    with pytest.raises(
        CustomerCommercialAccountPricingUnavailable,
        match="requires custom pricing",
    ):
        quote("50000.01")


@pytest.mark.parametrize(
    "invalid",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_price_book_rejects_invalid_cycle_balance(
    invalid: Decimal,
) -> None:
    with pytest.raises(
        (
            ValueError,
            CustomerCommercialAccountPricingUnavailable,
        )
    ):
        CustomerCommercialAccountPriceBook.quote(
            authoritative_cycle_balance_usd=invalid
        )


@pytest.mark.parametrize(
    "invalid",
    [
        1000,
        1000.0,
        True,
        "1000.00",
        None,
    ],
)
def test_price_book_requires_decimal_cycle_balance(
    invalid,
) -> None:
    with pytest.raises(TypeError):
        CustomerCommercialAccountPriceBook.quote(
            authoritative_cycle_balance_usd=invalid
        )


def test_quote_is_immutable():
    result = quote("7000.00")

    with pytest.raises(
        (
            AttributeError,
            TypeError,
        )
    ):
        result.licensed_account_cap_usd = 8000


def test_price_book_has_no_live_runtime_authority():
    result = quote("7000.00")

    for forbidden in (
        "live_balance_usd",
        "current_balance_usd",
        "trading_profit_usd",
        "trading_loss_usd",
        "external_deposit_usd",
        "external_withdrawal_usd",
        "grace_percent",
        "grace_ceiling_usd",
        "upgrade_required",
    ):
        assert not hasattr(
            result,
            forbidden,
        )


def test_price_book_emits_no_payment_fx_or_entitlement_truth():
    result = quote("7000.00")

    for forbidden in (
        "amount_minor",
        "currency",
        "fx_rate",
        "payment_intent_id",
        "order_id",
        "entitlement_id",
        "promotion_credit",
    ):
        assert not hasattr(
            result,
            forbidden,
        )
