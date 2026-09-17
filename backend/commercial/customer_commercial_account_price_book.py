"""
TODOBA Commercial Account USD Price Book.

Owns deterministic cycle-boundary commercial pricing truth.

Input:

    authoritative account balance captured at
    cycle start / renewal

Output:

    licensed account cap USD
    standard monthly price USD

This owner deliberately does not:

- observe live account balance
- classify trading profit or loss
- observe external deposits or withdrawals
- enforce runtime grace
- decide upgrades or downgrades
- perform FX conversion
- create commercial orders
- create payment intents
- grant entitlement
- apply promotions
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from decimal import ROUND_CEILING


_MINIMUM_AUTOMATIC_BALANCE_USD = Decimal("100.00")
_MAXIMUM_AUTOMATIC_BALANCE_USD = Decimal("50000.00")
_CAP_STEP_USD = Decimal("1000")


class CustomerCommercialAccountPricingUnavailable(
    ValueError,
):
    """
    Automatic commercial pricing is unavailable.
    """


@dataclass(
    frozen=True,
)
class CustomerCommercialAccountPriceQuote:
    """
    Immutable standard USD commercial tier quote.
    """

    licensed_account_cap_usd: int
    standard_monthly_price_usd: int

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "licensed_account_cap_usd",
            "standard_monthly_price_usd",
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


class CustomerCommercialAccountPriceBook:
    """
    Pure deterministic USD price-book authority.
    """

    @classmethod
    def quote(
        cls,
        *,
        authoritative_cycle_balance_usd: Decimal,
    ) -> CustomerCommercialAccountPriceQuote:

        balance = cls._validate_cycle_balance(
            authoritative_cycle_balance_usd
        )

        if (
            balance
            < _MINIMUM_AUTOMATIC_BALANCE_USD
        ):
            raise CustomerCommercialAccountPricingUnavailable(
                "authoritative cycle balance is "
                "below supported minimum."
            )

        if (
            balance
            > _MAXIMUM_AUTOMATIC_BALANCE_USD
        ):
            raise CustomerCommercialAccountPricingUnavailable(
                "authoritative cycle balance "
                "requires custom pricing."
            )

        cap_usd = cls._resolve_cap_usd(
            balance
        )

        price_usd = cls._resolve_monthly_price_usd(
            cap_usd
        )

        return CustomerCommercialAccountPriceQuote(
            licensed_account_cap_usd=cap_usd,
            standard_monthly_price_usd=price_usd,
        )

    @staticmethod
    def _validate_cycle_balance(
        value: Decimal,
    ) -> Decimal:

        if not isinstance(
            value,
            Decimal,
        ):
            raise TypeError(
                "authoritative_cycle_balance_usd "
                "must be Decimal."
            )

        if not value.is_finite():
            raise ValueError(
                "authoritative_cycle_balance_usd "
                "must be finite."
            )

        if value <= 0:
            raise ValueError(
                "authoritative_cycle_balance_usd "
                "must be positive."
            )

        return value

    @staticmethod
    def _resolve_cap_usd(
        balance: Decimal,
    ) -> int:

        cap = (
            balance
            / _CAP_STEP_USD
        ).to_integral_value(
            rounding=ROUND_CEILING
        ) * _CAP_STEP_USD

        return int(
            cap
        )

    @staticmethod
    def _resolve_monthly_price_usd(
        cap_usd: int,
    ) -> int:

        if cap_usd == 1000:
            return 50

        if 2000 <= cap_usd <= 5000:
            return (
                80
                + (
                    (cap_usd - 2000)
                    // 1000
                )
                * 30
            )

        if 6000 <= cap_usd <= 10000:
            return (
                190
                + (
                    (cap_usd - 6000)
                    // 1000
                )
                * 20
            )

        if 11000 <= cap_usd <= 25000:
            return (
                282
                + (
                    (cap_usd - 11000)
                    // 1000
                )
                * 12
            )

        if 26000 <= cap_usd <= 50000:
            return (
                458
                + (
                    (cap_usd - 26000)
                    // 1000
                )
                * 8
            )

        raise CustomerCommercialAccountPricingUnavailable(
            "automatic pricing tier is unavailable."
        )
