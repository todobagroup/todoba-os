"""
TODOBA Pending Order Production Validation

Validates the complete organizational pending-order flow:

TradingDepartment
    -> TradingRuntime
    -> TradingWorker
    -> LiveExecutionPipeline
    -> MT5 Demo
    -> PendingOrderRepository
    -> PendingOrderPersistence
    -> pending_orders.json

WARNING:
This script sends one real BUY LIMIT pending order to the
currently connected MT5 account.
"""

import asyncio
import json
import sys
from pathlib import Path

import MetaTrader5 as mt5


ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR),
    )


from backend.brain.memory import memory_engine
from backend.config import (
    BASE_DIR,
    MT5_BROKER_GOLD_SYMBOL,
)
from backend.task.task_factory import TaskFactory
from backend.trading.broker.mt5_client import MT5Client
from backend.trading.broker.mt5_safety import MT5Safety
from backend.trading.department.trading_department import (
    TradingDepartment,
)
from backend.trading.execution.live_execution_pipeline import (
    LiveExecutionPipeline,
)
from backend.trading.intent.trading_intent import (
    TradingIntent,
)
from backend.trading.pending.pending_order_record import (
    PendingOrderRecord,
)
from backend.trading.profile.trading_profile import (
    TradingProfile,
)


OPEN_TRADES_STORAGE_PATH = (
    BASE_DIR
    / "data"
    / "trading"
    / "open_trades.json"
)

PENDING_ORDERS_STORAGE_PATH = (
    OPEN_TRADES_STORAGE_PATH.parent
    / "pending_orders.json"
)

LOGICAL_SYMBOL = "XAUUSD"

ENTRY_DISTANCE = 10.0
STOP_DISTANCE = 5.0
TARGET_DISTANCE = 5.0


def print_step(
    label: str,
    value,
) -> None:
    print(
        f"[PASS] {label}: {value}"
    )


def build_prices(
    *,
    current_ask: float,
    digits: int,
) -> tuple[float, float, float]:
    entry = round(
        current_ask - ENTRY_DISTANCE,
        digits,
    )

    stop_loss = round(
        entry - STOP_DISTANCE,
        digits,
    )

    take_profit = round(
        entry + TARGET_DISTANCE,
        digits,
    )

    return (
        entry,
        stop_loss,
        take_profit,
    )


def read_persisted_payload() -> object:
    if not PENDING_ORDERS_STORAGE_PATH.exists():
        raise RuntimeError(
            "pending_orders.json was not created."
        )

    try:
        return json.loads(
            PENDING_ORDERS_STORAGE_PATH.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "pending_orders.json contains invalid JSON."
        ) from error


def payload_contains_order(
    *,
    payload: object,
    pending_order_id: str,
    broker_order: int,
) -> bool:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        default=str,
    )

    return (
        pending_order_id in serialized
        and str(broker_order) in serialized
    )


async def run_validation() -> None:
    print()
    print(
        "============================================"
    )
    print(
        "TODOBA PENDING ORDER PRODUCTION VALIDATION"
    )
    print(
        "============================================"
    )
    print(
        "WARNING: This sends one real pending order "
        "to the connected MT5 account."
    )
    print()

    mt5_client = MT5Client()
    department = None
    department_started = False

    try:
        if not mt5_client.connect():
            raise RuntimeError(
                "TODOBA could not connect to MT5."
            )

        print_step(
            "MT5 connected",
            True,
        )

        MT5Safety().validate()

        account = mt5_client.get_account_info()

        if account is None:
            raise RuntimeError(
                "TODOBA could not read MT5 account."
            )

        print_step(
            "MT5 account",
            account.login,
        )

        print_step(
            "MT5 server",
            account.server,
        )

        if not mt5.symbol_select(
            MT5_BROKER_GOLD_SYMBOL,
            True,
        ):
            raise RuntimeError(
                "Could not select broker symbol: "
                f"{MT5_BROKER_GOLD_SYMBOL}"
            )

        symbol_info = mt5.symbol_info(
            MT5_BROKER_GOLD_SYMBOL
        )

        if symbol_info is None:
            raise RuntimeError(
                "Could not read symbol information for "
                f"{MT5_BROKER_GOLD_SYMBOL}."
            )

        tick = mt5.symbol_info_tick(
            MT5_BROKER_GOLD_SYMBOL
        )

        if tick is None:
            raise RuntimeError(
                "Could not read current MT5 tick for "
                f"{MT5_BROKER_GOLD_SYMBOL}."
            )

        if tick.ask <= 0:
            raise RuntimeError(
                "Current MT5 ask price is invalid."
            )

        entry, stop_loss, take_profit = (
            build_prices(
                current_ask=tick.ask,
                digits=symbol_info.digits,
            )
        )

        print_step(
            "Broker symbol",
            MT5_BROKER_GOLD_SYMBOL,
        )

        print_step(
            "Current ask",
            tick.ask,
        )

        print_step(
            "BUY LIMIT entry",
            entry,
        )

        print_step(
            "Stop loss",
            stop_loss,
        )

        print_step(
            "Take profit",
            take_profit,
        )

        trading_profile = TradingProfile(
            profile_name=(
                "pending_order_production_validation"
            ),
            risk_percent=1.0,
            max_open_trades=10,
            allowed_symbols=(
                LOGICAL_SYMBOL,
            ),
            lot_policy_name="FIXED_001",
        )

        execution_pipeline = (
            LiveExecutionPipeline(
                profile=trading_profile,
                symbol_map={
                    LOGICAL_SYMBOL: (
                        MT5_BROKER_GOLD_SYMBOL
                    ),
                },
            )
        )

        department = TradingDepartment(
            execution_pipeline=(
                execution_pipeline
            ),
            open_trades_storage_path=(
                OPEN_TRADES_STORAGE_PATH
            ),
            memory=memory_engine,
            mt5_module=mt5,
            lifecycle_interval_seconds=5.0,
        )

        restored_trade_count = (
            await department.start()
        )

        department_started = True

        print_step(
            "TradingDepartment started",
            True,
        )

        print_step(
            "Open trades restored",
            restored_trade_count,
        )

        print_step(
            "Pending orders restored",
            department.pending_restored_count,
        )

        intent = TradingIntent(
            order_type="BUY LIMIT",
            asset=LOGICAL_SYMBOL,
            entry=entry,
            sl=stop_loss,
            tp=take_profit,
        )

        task = TaskFactory.create(
            task_type="trade",
            payload=intent,
        )

        execution_result = (
            department.runtime.dispatch(
                task
            )
        )

        if not isinstance(
            execution_result,
            PendingOrderRecord,
        ):
            raise RuntimeError(
                "Expected PendingOrderRecord, received "
                f"{type(execution_result).__name__}."
            )

        if execution_result.order is None:
            raise RuntimeError(
                "MT5 did not return a broker order ticket."
            )

        print_step(
            "Pending order sent",
            True,
        )

        print_step(
            "Broker order ticket",
            execution_result.order,
        )

        print_step(
            "Pending order ID",
            execution_result.pending_order_id,
        )

        print_step(
            "Pending order status",
            execution_result.status,
        )

        repository_records = (
            department.pending_repository.all()
        )

        repository_match = any(
            record.pending_order_id
            == execution_result.pending_order_id
            for record in repository_records
        )

        if not repository_match:
            raise RuntimeError(
                "PendingOrderRepository does not contain "
                "the new pending order."
            )

        print_step(
            "PendingOrderRepository updated",
            True,
        )

        persisted_payload = (
            read_persisted_payload()
        )

        if not payload_contains_order(
            payload=persisted_payload,
            pending_order_id=(
                execution_result.pending_order_id
            ),
            broker_order=execution_result.order,
        ):
            raise RuntimeError(
                "pending_orders.json does not contain "
                "the new pending order."
            )

        print_step(
            "pending_orders.json written",
            PENDING_ORDERS_STORAGE_PATH,
        )

        print()
        print(
            "============================================"
        )
        print(
            "TODOBA PRODUCTION VALIDATION: PASS"
        )
        print(
            "============================================"
        )
        print(
            "The pending order remains active on MT5."
        )
        print(
            "Cancel it manually after validation when "
            "it is no longer needed."
        )
        print()

    finally:
        if (
            department is not None
            and department_started
        ):
            await department.stop()

        mt5_client.disconnect()


def main() -> None:
    try:
        asyncio.run(
            run_validation()
        )

    except Exception as error:
        print()
        print(
            "============================================"
        )
        print(
            "TODOBA PRODUCTION VALIDATION: FAIL"
        )
        print(
            "============================================"
        )
        print(
            f"Reason: {error}"
        )
        print()

        raise


if __name__ == "__main__":
    main()