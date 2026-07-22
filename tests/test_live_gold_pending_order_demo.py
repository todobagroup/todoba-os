import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import MetaTrader5 as mt5

from backend.task.task_dispatcher import TaskDispatcher
from backend.task.task_factory import TaskFactory
from backend.task.task_queue import TaskQueue
from backend.trading.broker.mt5_client import MT5Client
from backend.trading.broker.mt5_safety import MT5Safety
from backend.trading.execution.live_execution_pipeline import (
    LiveExecutionPipeline,
)
from backend.trading.intent.trading_intent import TradingIntent
from backend.trading.profile.trading_profile import TradingProfile
from backend.workers.trading.trading_worker import TradingWorker
from backend.workers.worker_registry import WorkerRegistry


def main() -> None:
    print("=== LIVE GOLD BUY LIMIT DEMO ===")

    client = MT5Client()

    if not client.connect():
        print("Connect failed.")
        return

    worker = None

    try:
        MT5Safety().validate()

        broker_symbol = "GOLD.i#"

        if not mt5.symbol_select(
            broker_symbol,
            True,
        ):
            print(
                "Cannot select symbol:",
                broker_symbol,
            )
            return

        symbol_info = mt5.symbol_info(
            broker_symbol,
        )
        tick = mt5.symbol_info_tick(
            broker_symbol,
        )

        if symbol_info is None:
            print("Cannot read symbol info.")
            return

        if tick is None:
            print("Cannot read tick.")
            return

        digits = symbol_info.digits

        current_ask = round(
            tick.ask,
            digits,
        )

        entry = round(
            current_ask - 10.0,
            digits,
        )
        sl = round(
            entry - 5.0,
            digits,
        )
        tp = round(
            entry + 5.0,
            digits,
        )

        print(
            "Current ask:",
            current_ask,
        )
        print(
            "BUY LIMIT entry:",
            entry,
        )
        print(
            "Stop loss:",
            sl,
        )
        print(
            "Take profit:",
            tp,
        )

        profile = TradingProfile(
            profile_name="Founder Pending Demo",
            risk_percent=1.0,
            max_open_trades=5,
            allowed_symbols=("GOLD",),
            lot_policy_name="FIXED_001",
        )

        symbol_map = {
            "GOLD": broker_symbol,
        }

        intent = TradingIntent(
            order_type="BUY LIMIT",
            asset="GOLD",
            entry=entry,
            sl=sl,
            tp=tp,
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

        worker = TradingWorker(
            live_pipeline,
        )
        worker.start()

        registry.register(
            "trade",
            worker,
        )

        dispatcher = TaskDispatcher(
            queue,
            registry,
        )

        result = dispatcher.dispatch_next()

        print(result)
        print(
            "Pending order ID:",
            result.pending_order_id,
        )
        print(
            "Symbol:",
            result.symbol,
        )
        print(
            "Order type:",
            result.order_type,
        )
        print(
            "Volume:",
            result.volume,
        )
        print(
            "Entry:",
            result.entry,
        )
        print(
            "SL:",
            result.sl,
        )
        print(
            "TP:",
            result.tp,
        )
        print(
            "Status:",
            result.status,
        )
        print(
            "MT5 order:",
            result.order,
        )
        print(
            "Task status:",
            task.status,
        )
        print(
            "Task worker:",
            task.worker,
        )

    finally:
        if worker is not None:
            worker.stop()

        client.disconnect()


if __name__ == "__main__":
    main()