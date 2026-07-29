"""
TODOBA Execution Mission Intent Adapter Tests
"""

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_intent_adapter import (
    ExecutionMissionIntentAdapter,
)
from backend.trading.intent.trading_intent import (
    TradingIntent,
)


def test_execution_mission_converts_to_trading_intent():

    mission = ExecutionMission(
        mission_id="proof-intent-001",
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

    assert isinstance(
        intent,
        TradingIntent,
    )

    assert intent.order_type == "BUY LIMIT"
    assert intent.asset == "XAUUSD"
    assert intent.entry == 4100.0
    assert intent.sl == 4090.0
    assert intent.tp == 4120.0


def test_execution_mission_adapter_rejects_invalid_input():

    try:
        ExecutionMissionIntentAdapter().to_intent(
            "invalid"
        )

        assert False

    except TypeError:
        assert True