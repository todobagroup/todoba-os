import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.profile.trading_profile import TradingProfile
from backend.trading.execution.execution_pipeline import build_execution_request


def main():

    print("=== EXECUTION PIPELINE TEST ===")

    message = """
BUY GOLD NOW
SL 3330
TP 3345
"""

    profile = TradingProfile(
        profile_name="Founder Demo Gold",
        risk_percent=1.0,
        max_open_trades=1,
        allowed_symbols=("XAUUSD",),
        lot_policy_name="FIXED_001",
    )

    symbol_map = {
        "XAUUSD": "GOLD.i#",
    }

    request = build_execution_request(
        message=message,
        profile=profile,
        symbol_map=symbol_map,
        current_price=3335.00,
    )

    print(request)

    print(request["symbol"] == "GOLD.i#")
    print(request["volume"] == 0.01)
    print(request["price"] == 3335.00)
    print(request["sl"] == 3330.00)
    print(request["tp"] == 3345.00)


if __name__ == "__main__":
    main()