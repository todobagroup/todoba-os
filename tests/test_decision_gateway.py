"""
TODOBA Decision Gateway Tests

Proof:

TradingIntent
+
position and pending broker facts
->
Trading Decision
->
Task creation or rejection
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.task.task import Task
from backend.trading.decision.decision_gateway import (
    DecisionGateway,
)
from backend.trading.intent.trading_intent import (
    TradingIntent,
)


def build_intent() -> TradingIntent:
    return TradingIntent(
        order_type="BUY NOW",
        asset="XAUUSD",
        sl=4330.0,
        tp=4370.0,
    )


def test_gateway_creates_task_below_active_trade_limit():
    gateway = DecisionGateway()

    task, decision = (
        gateway.create_task_if_approved(
            intent=build_intent(),
            open_position_count=5,
            pending_order_count=4,
            max_open_trades=10,
            spread_ok=True,
            market_open=True,
            risk_ok=True,
        )
    )

    assert isinstance(
        task,
        Task,
    )
    assert decision.approved is True


def test_gateway_rejects_task_at_active_trade_limit():
    gateway = DecisionGateway()

    task, decision = (
        gateway.create_task_if_approved(
            intent=build_intent(),
            open_position_count=6,
            pending_order_count=4,
            max_open_trades=10,
            spread_ok=True,
            market_open=True,
            risk_ok=True,
        )
    )

    assert task is None
    assert decision.approved is False

    assert decision.reason == (
        "Maximum active trade limit reached: "
        "10/10 (positions=6, pending=4)."
    )