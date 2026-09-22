"""
TODOBA Customer Commercial In-Cycle Upgrade Quote Authority.

Owns pure deterministic upgrade pricing from:
- current licensed account cap USD
- current standard monthly price USD
- target licensed account cap USD

This owner deliberately does not:
- apply promotions
- prorate
- create payment intents
- settle payments
- mutate entitlements
- mutate deployments
- control runtime execution
"""

from dataclasses import dataclass

from backend.commercial.customer_commercial_account_price_book import (
    CustomerCommercialAccountPriceBook,
)


@dataclass(
    frozen=True,
)
class CustomerCommercialUpgradeQuote:
    current_licensed_account_cap_usd: int
    current_standard_monthly_price_usd: int
    target_licensed_account_cap_usd: int
    target_standard_monthly_price_usd: int
    amount_due_usd: int

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "current_licensed_account_cap_usd",
            "current_standard_monthly_price_usd",
            "target_licensed_account_cap_usd",
            "target_standard_monthly_price_usd",
            "amount_due_usd",
        ):
            value = getattr(
                self,
                name,
            )

            if (
                isinstance(
                    value,
                    bool,
                )
                or not isinstance(
                    value,
                    int,
                )
            ):
                raise TypeError(
                    f"{name} must be int."
                )

            if value <= 0:
                raise ValueError(
                    f"{name} must be positive."
                )


class CustomerCommercialUpgradeQuoteService:
    """
    Pure in-cycle upgrade quote authority.
    """

    @classmethod
    def quote(
        cls,
        *,
        current_licensed_account_cap_usd: int,
        current_standard_monthly_price_usd: int,
        target_licensed_account_cap_usd: int,
    ) -> CustomerCommercialUpgradeQuote:
        current_quote = (
            CustomerCommercialAccountPriceBook.quote_for_cap(
                licensed_account_cap_usd=(
                    current_licensed_account_cap_usd
                ),
            )
        )

        if (
            current_standard_monthly_price_usd
            != current_quote.standard_monthly_price_usd
        ):
            raise RuntimeError(
                "current standard monthly price "
                "does not match price-book truth."
            )

        if (
            target_licensed_account_cap_usd
            <= current_licensed_account_cap_usd
        ):
            raise ValueError(
                "target licensed account cap must be "
                "strictly higher than current cap."
            )

        target_quote = (
            CustomerCommercialAccountPriceBook.quote_for_cap(
                licensed_account_cap_usd=(
                    target_licensed_account_cap_usd
                ),
            )
        )

        amount_due_usd = (
            target_quote.standard_monthly_price_usd
            - current_quote.standard_monthly_price_usd
        )

        if amount_due_usd <= 0:
            raise RuntimeError(
                "upgrade amount due must be positive."
            )

        return CustomerCommercialUpgradeQuote(
            current_licensed_account_cap_usd=(
                current_quote.licensed_account_cap_usd
            ),
            current_standard_monthly_price_usd=(
                current_quote.standard_monthly_price_usd
            ),
            target_licensed_account_cap_usd=(
                target_quote.licensed_account_cap_usd
            ),
            target_standard_monthly_price_usd=(
                target_quote.standard_monthly_price_usd
            ),
            amount_due_usd=amount_due_usd,
        )
