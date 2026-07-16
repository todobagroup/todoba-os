"""
TODOBA Trading Intent

Represents the complete trading intention
before execution.

Order type information must remain intact
from Signal to MT5.
"""

from dataclasses import dataclass
from typing import Optional


SUPPORTED_ORDER_TYPES = (
    "BUY NOW",
    "SELL NOW",
    "BUY LIMIT",
    "SELL LIMIT",
    "BUY STOP",
    "SELL STOP",
)


@dataclass(frozen=True)
class TradingIntent:
    """
    Immutable organizational trading intention.
    """

    order_type: str

    asset: str

    sl: float

    tp: float

    entry: Optional[float] = None

    def __post_init__(self) -> None:
        normalized_order_type = (
            self.order_type
            .strip()
            .upper()
        )

        object.__setattr__(
            self,
            "order_type",
            normalized_order_type,
        )

        if (
            normalized_order_type
            not in SUPPORTED_ORDER_TYPES
        ):
            raise ValueError(
                "Unsupported order type: "
                f"{normalized_order_type}"
            )

        if (
            normalized_order_type
            not in ("BUY NOW", "SELL NOW")
            and self.entry is None
        ):
            raise ValueError(
                "Pending order requires entry price."
            )

    @property
    def action(self) -> str:
        """
        Return BUY or SELL for compatibility with
        organizational components that only need direction.
        """

        return self.order_type.split(
            maxsplit=1
        )[0]