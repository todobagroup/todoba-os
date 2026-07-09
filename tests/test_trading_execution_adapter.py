import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.intent.trading_intent import TradingIntent
from backend.trading.execution.trading_execution_adapter import (
    TradingExecutionAdapter,
)


def main():

    print("=== TRADING EXECUTION ADAPTER TEST ===")

    intent = TradingIntent(
        action="BUY",
        asset="GOLD",
        sl=3330,
        tp=3345,
    )

    adapter = TradingExecutionAdapter()

    plan = adapter.to_execution_plan(intent)

    print(plan.symbol)
    print(plan.order_type)
    print(plan.sl)
    print(plan.tp)

    print(plan.comment)


if __name__ == "__main__":
    main()