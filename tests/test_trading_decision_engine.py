import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.decision.decision_engine import (
    TradingDecisionEngine,
)


def main():

    print("=== TRADING DECISION ENGINE TEST ===")

    engine = TradingDecisionEngine()

    result = engine.decide(
        has_open_position=False,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    print(result.approved)

    print(result.reason)

    reject = engine.decide(
        has_open_position=True,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    print(reject.approved)

    print(reject.reason)


if __name__ == "__main__":
    main()