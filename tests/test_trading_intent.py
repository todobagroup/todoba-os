import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.intent.trading_intent import TradingIntent
from backend.trading.intent.intent_validator import IntentValidator


def main():

    print("=== TRADING INTENT TEST ===")

    intent = TradingIntent(
        action="BUY",
        asset="GOLD",
        sl=3330,
        tp=3345,
    )

    validator = IntentValidator()

    print(validator.validate(intent))

    print(intent.action)

    print(intent.asset)

    print(intent.sl)

    print(intent.tp)


if __name__ == "__main__":
    main()