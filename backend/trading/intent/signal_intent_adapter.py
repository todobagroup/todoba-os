"""
TODOBA Signal Intent Adapter

Converts an approved trading Signal into TradingIntent.

The adapter preserves the complete order type from
Signal through organizational execution.
"""

from backend.trading.intent.trading_intent import (
    TradingIntent,
)
from backend.trading.models.signal import (
    Signal,
)


class SignalIntentAdapter:
    """
    Convert a trading Signal into TradingIntent.

    This adapter does not:
    - approve the intent;
    - create a Task;
    - execute a trade.
    """

    def to_intent(
        self,
        signal: Signal,
    ) -> TradingIntent:
        if not isinstance(
            signal,
            Signal,
        ):
            raise TypeError(
                "SignalIntentAdapter requires Signal."
            )

        return TradingIntent(
            order_type=signal.order_type,
            asset=signal.symbol,
            entry=signal.entry,
            sl=signal.sl,
            tp=signal.tp,
        )