"""
TODOBA Trade Outcome Evaluator

Interprets broker evidence from ClosedTradeObservation.

Observation records what happened.
Evaluation determines what the result means.

This evaluator does not:
- create TradeExperience;
- write to Memory;
- change broker data.
"""

from dataclasses import dataclass

from backend.trading.lifecycle.closed_trade_observation import (
    ClosedTradeObservation,
)


@dataclass(frozen=True)
class TradeOutcomeEvaluation:
    """
    Interpreted result of one closed trade.
    """

    outcome: str
    reason: str
    net_profit: float
    close_reason: str


class TradeOutcomeEvaluator:
    """
    Evaluate a closed trade from broker evidence.

    Outcomes:

    profit
        Net profit is greater than the breakeven tolerance.

    loss
        Net profit is lower than the negative tolerance.

    breakeven
        Net profit is inside the configured tolerance.
    """

    def __init__(
        self,
        breakeven_tolerance: float = 0.01,
    ):
        if breakeven_tolerance < 0:
            raise ValueError(
                "breakeven_tolerance cannot be negative."
            )

        self.breakeven_tolerance = (
            breakeven_tolerance
        )

    def evaluate(
        self,
        observation: ClosedTradeObservation,
    ) -> TradeOutcomeEvaluation:
        if not isinstance(
            observation,
            ClosedTradeObservation,
        ):
            raise TypeError(
                "TradeOutcomeEvaluator requires "
                "ClosedTradeObservation."
            )

        net_profit = observation.net_profit

        if net_profit > self.breakeven_tolerance:
            outcome = "profit"

        elif net_profit < -self.breakeven_tolerance:
            outcome = "loss"

        else:
            outcome = "breakeven"

        reason = self._build_reason(
            outcome=outcome,
            close_reason=observation.close_reason,
        )

        return TradeOutcomeEvaluation(
            outcome=outcome,
            reason=reason,
            net_profit=net_profit,
            close_reason=observation.close_reason,
        )

    def _build_reason(
        self,
        *,
        outcome: str,
        close_reason: str,
    ) -> str:
        reason_map = {
            "take_profit": "Take profit reached.",
            "stop_loss": "Stop loss reached.",
            "stop_out": "Position closed by broker stop out.",
            "manual_desktop": (
                "Position closed manually from desktop."
            ),
            "manual_mobile": (
                "Position closed manually from mobile."
            ),
            "manual_web": (
                "Position closed manually from web."
            ),
            "expert": (
                "Position closed by an automated expert."
            ),
            "unknown": (
                "Broker did not provide a recognized "
                "close reason."
            ),
        }

        close_description = reason_map.get(
            close_reason,
            reason_map["unknown"],
        )

        outcome_description = {
            "profit": "The trade finished with net profit.",
            "loss": "The trade finished with net loss.",
            "breakeven": (
                "The trade finished near breakeven."
            ),
        }[outcome]

        return (
            f"{outcome_description} "
            f"{close_description}"
        )
