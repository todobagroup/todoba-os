"""
Tests for TODOBA TradeOutcomeEvaluator.
"""

from datetime import datetime, timezone

import pytest

from backend.trading.lifecycle.closed_trade_observation import (
    ClosedTradeObservation,
)
from backend.trading.lifecycle.trade_outcome_evaluator import (
    TradeOutcomeEvaluator,
)


def create_observation(
    *,
    net_profit: float,
    close_reason: str,
) -> ClosedTradeObservation:
    return ClosedTradeObservation(
        position_id=90001,
        close_deal_id=70002,
        order_id=80002,
        symbol="GOLD.i#",
        action="BUY",
        volume=0.01,
        close_price=4125.0,
        closed_at=datetime.now(
            timezone.utc
        ),
        gross_profit=net_profit,
        commission=0.0,
        swap=0.0,
        fee=0.0,
        net_profit=net_profit,
        close_reason=close_reason,
        comment="TODOBA",
    )


def test_profitable_trade_is_evaluated():
    evaluator = TradeOutcomeEvaluator()

    result = evaluator.evaluate(
        create_observation(
            net_profit=19.40,
            close_reason="take_profit",
        )
    )

    assert result.outcome == "profit"
    assert result.net_profit == 19.40
    assert result.close_reason == "take_profit"

    assert (
        "net profit"
        in result.reason
    )

    assert (
        "Take profit reached"
        in result.reason
    )


def test_losing_trade_is_evaluated():
    evaluator = TradeOutcomeEvaluator()

    result = evaluator.evaluate(
        create_observation(
            net_profit=-10.50,
            close_reason="stop_loss",
        )
    )

    assert result.outcome == "loss"

    assert (
        "net loss"
        in result.reason
    )

    assert (
        "Stop loss reached"
        in result.reason
    )


def test_near_zero_trade_is_breakeven():
    evaluator = TradeOutcomeEvaluator(
        breakeven_tolerance=0.05
    )

    result = evaluator.evaluate(
        create_observation(
            net_profit=0.02,
            close_reason="manual_desktop",
        )
    )

    assert result.outcome == "breakeven"


def test_evaluator_rejects_invalid_input():
    evaluator = TradeOutcomeEvaluator()

    with pytest.raises(
        TypeError,
        match="requires ClosedTradeObservation",
    ):
        evaluator.evaluate(
            "not-an-observation"
        )


def test_negative_tolerance_is_rejected():
    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        TradeOutcomeEvaluator(
            breakeven_tolerance=-0.01
        )
