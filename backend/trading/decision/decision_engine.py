"""
TODOBA Trading Decision Engine

Approves valid trading opportunities while enforcing
the configured maximum number of active trades.

An active trade is either:

- an open broker position
- an active pending broker order
"""

from backend.trading.decision.decision_result import (
    DecisionResult,
)


class TradingDecisionEngine:
    """
    First-generation organizational decision engine.
    """

    def decide(
        self,
        *,
        open_position_count: int,
        pending_order_count: int,
        max_open_trades: int,
        spread_ok: bool,
        market_open: bool,
        risk_ok: bool,
    ) -> DecisionResult:

        if not isinstance(
            open_position_count,
            int,
        ):
            raise TypeError(
                "open_position_count must be int."
            )

        if open_position_count < 0:
            raise ValueError(
                "open_position_count cannot be negative."
            )

        if not isinstance(
            pending_order_count,
            int,
        ):
            raise TypeError(
                "pending_order_count must be int."
            )

        if pending_order_count < 0:
            raise ValueError(
                "pending_order_count cannot be negative."
            )

        if not isinstance(
            max_open_trades,
            int,
        ):
            raise TypeError(
                "max_open_trades must be int."
            )

        if max_open_trades <= 0:
            raise ValueError(
                "max_open_trades must be greater than zero."
            )

        if not market_open:
            return DecisionResult(
                False,
                "Market is closed.",
            )

        if not spread_ok:
            return DecisionResult(
                False,
                "Spread too large.",
            )

        if not risk_ok:
            return DecisionResult(
                False,
                "Risk rejected.",
            )

        active_trade_count = (
            open_position_count
            + pending_order_count
        )

        if (
            active_trade_count
            >= max_open_trades
        ):
            return DecisionResult(
                False,
                (
                    "Maximum active trade limit reached: "
                    f"{active_trade_count}/"
                    f"{max_open_trades} "
                    f"(positions={open_position_count}, "
                    f"pending={pending_order_count})."
                ),
            )

        return DecisionResult(
            True,
            "Approved.",
        )