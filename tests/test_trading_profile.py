import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.profile.trading_profile import TradingProfile


def main():
    print("=== TRADING PROFILE TEST ===")

    profile = TradingProfile(
        profile_name="Founder Gold Profile",
        risk_percent=1.0,
        max_open_trades=1,
        allowed_symbols=("XAUUSD",),
        lot_policy_name="FIXED_001",
    )

    print(profile)
    print(f"Profile OK: {profile.profile_name == 'Founder Gold Profile'}")
    print(f"Allowed XAUUSD: {'XAUUSD' in profile.allowed_symbols}")


if __name__ == "__main__":
    main()