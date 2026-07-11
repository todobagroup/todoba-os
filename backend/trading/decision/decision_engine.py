"""
TODOBA Trading Decision Engine

First generation rule engine.
"""

from backend.trading.decision.decision_result import DecisionResult


class TradingDecisionEngine:

    def decide(
        self,
        *,
        has_open_position: bool,
        spread_ok: bool,
        market_open: bool,
        risk_ok: bool,
    ):

        if not market_open:
            return DecisionResult(
                False,
                "Market is closed."
            )

        if not spread_ok:
            return DecisionResult(
                False,
                "Spread too large."
            )

        if not risk_ok:
            return DecisionResult(
                False,
                "Risk rejected."
            )

        if has_open_position:
            return DecisionResult(
                False,
                "Position already exists."
            )

        return DecisionResult(
            True,
            "Approved."
        )