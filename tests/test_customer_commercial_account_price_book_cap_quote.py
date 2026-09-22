from backend.commercial.customer_commercial_account_price_book import (
    CustomerCommercialAccountPriceBook,
    CustomerCommercialAccountPricingUnavailable,
)

import pytest


def test_quote_for_cap_reuses_standard_price_book_truth():
    quote = CustomerCommercialAccountPriceBook.quote_for_cap(
        licensed_account_cap_usd=7000,
    )

    assert quote.licensed_account_cap_usd == 7000
    assert quote.standard_monthly_price_usd == 210


@pytest.mark.parametrize(
    "invalid_cap",
    (
        0,
        -1000,
        1500,
        51000,
        True,
        1000.0,
        "1000",
        None,
    ),
)
def test_quote_for_cap_rejects_invalid_or_unsupported_cap(
    invalid_cap,
):
    with pytest.raises(
        (
            TypeError,
            ValueError,
            CustomerCommercialAccountPricingUnavailable,
        )
    ):
        CustomerCommercialAccountPriceBook.quote_for_cap(
            licensed_account_cap_usd=invalid_cap,
        )
