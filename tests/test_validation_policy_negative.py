import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.models.signal import Signal
from backend.trading.profile.trading_profile import TradingProfile
from backend.trading.validation.validation_policy import validate


def main():
    print("=== VALIDATION POLICY NEGATIVE TEST ===")

    profile = TradingProfile(
        profile_name="Founder",
        risk_percent=0,
        max_open_trades=0,
        allowed_symbols=("XAUUSD",),
        lot_policy_name="FIXED_001",
    )

    signal = Signal(
        order_type="BUY",
        symbol="BTCUSD",
        entry=3320,
        sl=3310,
        tp=3340,
    )

    result = validate(signal, profile)

    print(result)

    print("Symbol rejected:", "Symbol not allowed." in result.errors)
    print("Risk rejected:", "Invalid risk percent." in result.errors)
    print("Max trades rejected:", "Invalid max open trades." in result.errors)
    print("Validation failed:", result.passed is False)


if __name__ == "__main__":
    main()