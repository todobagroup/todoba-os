"""
TODOBA Trading Decision Engine Tests

Proof:

open broker positions
+
active pending broker orders
->
maximum active trade policy
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.decision.decision_engine import (
    TradingDecisionEngine,
)


def test_approves_below_maximum_active_trade_limit():
    engine = TradingDecisionEngine()

    result = engine.decide(
        open_position_count=5,
        pending_order_count=4,
        max_open_trades=10,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.approved is True
    assert result.reason == "Approved."


def test_rejects_when_positions_and_pending_reach_limit():
    engine = TradingDecisionEngine()

    result = engine.decide(
        open_position_count=6,
        pending_order_count=4,
        max_open_trades=10,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.approved is False

    assert result.reason == (
        "Maximum active trade limit reached: "
        "10/10 (positions=6, pending=4)."
    )


@pytest.mark.parametrize(
    (
        "open_position_count",
        "pending_order_count",
    ),
    [
        (10, 0),
        (0, 10),
        (7, 3),
    ],
)
def test_rejects_all_combinations_at_limit(
    open_position_count,
    pending_order_count,
):
    engine = TradingDecisionEngine()

    result = engine.decide(
        open_position_count=open_position_count,
        pending_order_count=pending_order_count,
        max_open_trades=10,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert result.approved is False


def test_rejects_negative_pending_order_count():
    engine = TradingDecisionEngine()

    with pytest.raises(
        ValueError,
        match=(
            "pending_order_count cannot be negative."
        ),
    ):
        engine.decide(
            open_position_count=0,
            pending_order_count=-1,
            max_open_trades=10,
            spread_ok=True,
            market_open=True,
            risk_ok=True,
        )