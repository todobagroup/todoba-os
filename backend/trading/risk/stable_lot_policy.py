"""
TODOBA Stable Lot Policy

Simple and predictable lot sizing for TODOBA Stable.

Policy:

- Equity below 500 USD:
  recommend a Cent account.
  Standard accounts still use 0.01 lot.

- 500 to 1499.99 USD:
  0.01 lot.

- 1500 to 2499.99 USD:
  0.02 lot.

- Each additional 1000 USD tier:
  add 0.01 lot.

- Maximum supported equity:
  100000 USD.

- Maximum Stable volume:
  1.00 lot.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class StableLotResult:
    """
    Position-sizing decision for TODOBA Stable.
    """

    approved: bool
    volume: float
    equity: float
    capital_tier: int
    cent_account_recommended: bool
    reason: str


def calculate_stable_lot(
    *,
    equity: float,
    broker_minimum_volume: float = 0.01,
    broker_volume_step: float = 0.01,
    broker_maximum_volume: float = 100.0,
) -> StableLotResult:
    """
    Calculate the Stable V1 volume from account equity.
    """

    if equity <= 0:
        raise ValueError(
            "equity must be greater than zero."
        )

    if equity > 100000:
        raise ValueError(
            "Stable V1 supports equity up to 100000 USD."
        )

    if broker_minimum_volume <= 0:
        raise ValueError(
            "broker_minimum_volume must be greater than zero."
        )

    if broker_volume_step <= 0:
        raise ValueError(
            "broker_volume_step must be greater than zero."
        )

    if broker_maximum_volume < broker_minimum_volume:
        raise ValueError(
            "broker_maximum_volume cannot be smaller "
            "than broker_minimum_volume."
        )

    cent_recommended = equity < 500.0

    if equity < 1500.0:
        capital_tier = 1
    else:
        capital_tier = math.floor(
            (equity + 500.0) / 1000.0
        )

    raw_volume = capital_tier * 0.01

    stable_maximum_volume = 1.00

    allowed_maximum = min(
        stable_maximum_volume,
        broker_maximum_volume,
    )

    volume_steps = math.floor(
        (raw_volume + 1e-12)
        / broker_volume_step
    )

    volume = round(
        volume_steps * broker_volume_step,
        8,
    )

    volume = max(
        volume,
        broker_minimum_volume,
    )

    volume = min(
        volume,
        allowed_maximum,
    )

    if volume < broker_minimum_volume:
        return StableLotResult(
            approved=False,
            volume=0.0,
            equity=equity,
            capital_tier=capital_tier,
            cent_account_recommended=(
                cent_recommended
            ),
            reason=(
                "No valid broker volume is available."
            ),
        )

    reason = (
        f"Stable capital tier {capital_tier}: "
        f"{volume:.2f} lot."
    )

    if cent_recommended:
        reason += (
            " Cent account is recommended "
            "for equity below 500 USD."
        )

    return StableLotResult(
        approved=True,
        volume=volume,
        equity=equity,
        capital_tier=capital_tier,
        cent_account_recommended=(
            cent_recommended
        ),
        reason=reason,
    )