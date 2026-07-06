import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.models.signal import Signal
from backend.trading.profile.trading_profile import TradingProfile
from backend.trading.execution.execution_planner import create_plan


def main():

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

    plan = create_plan(signal, profile)

    print(plan)

    print(plan.lot == 0.01)

    print(plan.symbol == "XAUUSD")

    print(plan.comment == "TODOBA")


if __name__ == "__main__":
    main()