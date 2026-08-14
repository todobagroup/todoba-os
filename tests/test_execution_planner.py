import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_planner import (
    create_plan,
)
from backend.trading.models.signal import Signal
from backend.trading.profile.trading_profile import (
    TradingProfile,
)


def test_execution_plan_uses_todoba_signature() -> None:
    profile = TradingProfile(
        profile_name="Founder",
        risk_percent=1.0,
        max_open_trades=1,
        allowed_symbols=("XAUUSD",),
        lot_policy_name="FIXED_001",
    )

    signal = Signal(
        order_type="BUY",
        symbol="XAUUSD",
        entry=3320,
        sl=3310,
        tp=3340,
    )

    plan = create_plan(
        signal,
        profile,
    )

    assert plan.lot == 0.01
    assert plan.symbol == "XAUUSD"
    assert plan.comment == "TODOBA"