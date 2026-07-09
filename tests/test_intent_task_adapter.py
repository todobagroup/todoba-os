import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.intent.trading_intent import TradingIntent
from backend.trading.intent.intent_task_adapter import IntentTaskAdapter


def main():

    print("=== INTENT TASK ADAPTER TEST ===")

    intent = TradingIntent(
        action="BUY",
        asset="GOLD",
        sl=3330,
        tp=3345,
    )

    adapter = IntentTaskAdapter()

    task = adapter.to_task(intent)

    print(task.task_type)
    print(task.payload.action)
    print(task.payload.asset)
    print(task.payload.sl)
    print(task.payload.tp)


if __name__ == "__main__":
    main()