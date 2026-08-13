"""
TODOBA Trade Task Execution Mission Adapter Tests

Proof:
Approved trade Task
->
ExecutionMission

The adapter only translates an approved trade Task.
It does not execute orders or deliver missions.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.task.task_factory import TaskFactory
from backend.trading.execution.trade_task_execution_mission_adapter import (
    TradeTaskExecutionMissionAdapter,
)
from backend.trading.intent.trading_intent import TradingIntent


def test_approved_trade_task_can_become_execution_mission():
    intent = TradingIntent(
        order_type="SELL NOW",
        asset="XAUUSD",
        sl=4334.0,
        tp=4303.0,
    )

    task = TaskFactory.create(
        task_type="trade",
        payload=intent,
    )

    adapter = TradeTaskExecutionMissionAdapter()

    mission = adapter.to_mission(
        task,
        mission_id="proof087-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        volume=0.01,
        magic_number=10001,
        comment="TODOBA proof087",
        created_at="2026-08-10T00:00:00Z",
        expires_at="2026-08-10T00:02:00Z",
        sequence=87,
    )

    assert mission.mission_id == "proof087-001"
    assert mission.agent_id == "trusted-agent-001"
    assert mission.account_fingerprint == "demo-account"

    assert mission.symbol == "XAUUSD"
    assert mission.order_type == "SELL NOW"
    assert mission.volume == 0.01
    assert mission.entry is None
    assert mission.sl == 4334.0
    assert mission.tp == 4303.0

    assert mission.magic_number == 10001
    assert mission.comment == "TODOBA proof087"
    assert mission.sequence == 87