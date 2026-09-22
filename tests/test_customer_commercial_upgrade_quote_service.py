import pytest

from backend.commercial.customer_commercial_account_price_book import (
    CustomerCommercialAccountPricingUnavailable,
)
from backend.commercial.customer_commercial_upgrade_quote_service import (
    CustomerCommercialUpgradeQuoteService,
)


def test_upgrade_quote_uses_full_standard_tier_difference():
    quote = CustomerCommercialUpgradeQuoteService.quote(
        current_licensed_account_cap_usd=1000,
        current_standard_monthly_price_usd=50,
        target_licensed_account_cap_usd=2000,
    )

    assert quote.current_licensed_account_cap_usd == 1000
    assert quote.current_standard_monthly_price_usd == 50
    assert quote.target_licensed_account_cap_usd == 2000
    assert quote.target_standard_monthly_price_usd == 80
    assert quote.amount_due_usd == 30


def test_larger_upgrade_uses_full_standard_difference():
    quote = CustomerCommercialUpgradeQuoteService.quote(
        current_licensed_account_cap_usd=5000,
        current_standard_monthly_price_usd=170,
        target_licensed_account_cap_usd=10000,
    )

    assert quote.target_standard_monthly_price_usd == 270
    assert quote.amount_due_usd == 100


@pytest.mark.parametrize(
    "target_cap",
    (
        1000,
        500,
    ),
)
def test_target_must_be_strictly_higher_than_current(
    target_cap: int,
):
    with pytest.raises(
        ValueError,
        match="target.*higher",
    ):
        CustomerCommercialUpgradeQuoteService.quote(
            current_licensed_account_cap_usd=1000,
            current_standard_monthly_price_usd=50,
            target_licensed_account_cap_usd=target_cap,
        )


def test_current_standard_price_must_match_price_book_truth():
    with pytest.raises(
        RuntimeError,
        match="current standard monthly price",
    ):
        CustomerCommercialUpgradeQuoteService.quote(
            current_licensed_account_cap_usd=1000,
            current_standard_monthly_price_usd=35,
            target_licensed_account_cap_usd=2000,
        )


def test_unsupported_target_cap_is_rejected():
    with pytest.raises(
        CustomerCommercialAccountPricingUnavailable,
    ):
        CustomerCommercialUpgradeQuoteService.quote(
            current_licensed_account_cap_usd=1000,
            current_standard_monthly_price_usd=50,
            target_licensed_account_cap_usd=1500,
        )


def test_upgrade_quote_emits_no_payment_promo_or_runtime_authority():
    quote = CustomerCommercialUpgradeQuoteService.quote(
        current_licensed_account_cap_usd=1000,
        current_standard_monthly_price_usd=50,
        target_licensed_account_cap_usd=2000,
    )

    for forbidden in (
        "promotion_credit",
        "proration",
        "payment_intent_id",
        "settlement_id",
        "entitlement_id",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
    ):
        assert not hasattr(
            quote,
            forbidden,
        )
