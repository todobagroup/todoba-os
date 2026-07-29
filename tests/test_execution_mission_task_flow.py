"""
TODOBA Execution Mission Task Flow Tests

Proofs:
ExecutionMission
    ->
TradingIntent
    ->
Task
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.task.task import Task
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_intent_adapter import (
    ExecutionMissionIntentAdapter,
)
from backend.trading.intent.intent_task_adapter import (
    IntentTaskAdapter,
)


def test_execution_mission_can_become_trade_task():

    mission = ExecutionMission(
        mission_id="proof-flow-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.01,
        entry=4100.0,
        sl=4090.0,
        tp=4120.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-07-29T00:00:00",
        expires_at="2026-07-29T01:00:00",
        sequence=1,
    )

    intent = (
        ExecutionMissionIntentAdapter()
        .to_intent(mission)
    )

    task = (
        IntentTaskAdapter()
        .to_task(intent)
    )

    assert isinstance(
        task,
        Task,
    )

    assert task.task_type == "trade"

    assert task.payload.asset == "XAUUSD"

    assert task.payload.order_type == "BUY LIMIT"

    assert task.payload.entry == 4100.0

    assert task.payload.sl == 4090.0

    assert task.payload.tp == 4120.0