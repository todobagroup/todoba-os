"""
TODOBA Signal Intent Adapter

Converts an approved trading Signal into TradingIntent.

The adapter separates signal interpretation from
organizational decision and task creation.
"""

from backend.trading.intent.trading_intent import TradingIntent
from backend.trading.models.signal import Signal


class SignalIntentAdapter:
    """
    Convert the trading domain Signal into TradingIntent.

    This adapter does not:
    - approve the intent;
    - create a Task;
    - execute a trade.
    """

    def to_intent(
        self,
        signal: Signal,
    ) -> TradingIntent:
        if not isinstance(signal, Signal):
            raise TypeError(
                "SignalIntentAdapter requires Signal."
            )

        action = signal.order_type.replace(
            " NOW",
            "",
        ).strip().upper()

        if action not in ("BUY", "SELL"):
            raise ValueError(
                f"Unsupported trading action: {action}"
            )

        return TradingIntent(
            action=action,
            asset=signal.symbol,
            entry=signal.entry,
            sl=signal.sl,
            tp=signal.tp,
        )