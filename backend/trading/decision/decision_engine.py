"""
TODOBA Trading Decision Engine

Approves valid trading opportunities while enforcing
the configured maximum number of open positions.
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

        if (
            open_position_count
            >= max_open_trades
        ):
            return DecisionResult(
                False,
                (
                    "Maximum open trade limit reached: "
                    f"{open_position_count}/"
                    f"{max_open_trades}."
                ),
            )

        return DecisionResult(
            True,
            "Approved.",
        )