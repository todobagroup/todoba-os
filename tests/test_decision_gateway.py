import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.decision.decision_gateway import DecisionGateway
from backend.trading.intent.trading_intent import TradingIntent


def main():

    print("=== DECISION GATEWAY TEST ===")

    gateway = DecisionGateway()

    intent = TradingIntent(
        action="BUY",
        asset="GOLD",
        sl=3330,
        tp=3345,
    )

    task, decision = gateway.create_task_if_approved(
        intent=intent,
        has_open_position=False,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    print(task is not None)
    print(decision.approved)

    task2, decision2 = gateway.create_task_if_approved(
        intent=intent,
        has_open_position=True,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    print(task2 is None)
    print(decision2.reason)


if __name__ == "__main__":
    main()