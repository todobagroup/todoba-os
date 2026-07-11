import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import MetaTrader5 as mt5

from backend.task.task_factory import TaskFactory
from backend.task.task_queue import TaskQueue
from backend.task.task_dispatcher import TaskDispatcher
from backend.workers.worker_registry import WorkerRegistry
from backend.workers.trading.trading_worker import TradingWorker

from backend.trading.intent.trading_intent import TradingIntent
from backend.trading.profile.trading_profile import TradingProfile
from backend.trading.execution.live_execution_pipeline import LiveExecutionPipeline
from backend.trading.broker.mt5_client import MT5Client
from backend.trading.broker.mt5_safety import MT5Safety


def main():

    print("=== LIVE GOLD TASK ENGINE DEMO ===")

    client = MT5Client()

    if not client.connect():
        print("Connect failed.")
        return

    MT5Safety().validate()

    broker_symbol = "GOLD.i#"
    mt5.symbol_select(broker_symbol, True)

    tick = mt5.symbol_info_tick(broker_symbol)

    if tick is None:
        print("Cannot read tick.")
        client.disconnect()
        return

    price = tick.ask

    profile = TradingProfile(
        profile_name="Founder Demo Gold",
        risk_percent=1.0,
        max_open_trades=1,
        allowed_symbols=("GOLD",),
        lot_policy_name="FIXED_001",
    )

    symbol_map = {
        "GOLD": "GOLD.i#",
    }

    intent = TradingIntent(
        action="BUY",
        asset="GOLD",
        sl=price - 5,
        tp=price + 5,
    )

    task = TaskFactory.create(
        task_type="trade",
        payload=intent,
    )

    queue = TaskQueue()
    queue.push(task)

    registry = WorkerRegistry()

    live_pipeline = LiveExecutionPipeline(
        profile=profile,
        symbol_map=symbol_map,
    )

    worker = TradingWorker(live_pipeline)
    worker.start()

    registry.register("trade", worker)

    dispatcher = TaskDispatcher(queue, registry)

    result = dispatcher.dispatch_next()

    print(result)
    print("Trade ID:", result.trade_id)
    print("Status:", result.status)
    print("Order:", result.order)
    print("Deal:", result.deal)
    print("Task status:", task.status)
    print("Task worker:", task.worker)

    worker.stop()
    client.disconnect()


if __name__ == "__main__":
    main()