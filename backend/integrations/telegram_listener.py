"""
TODOBA Telegram Listener

Supports two explicit execution modes:

DRY_RUN
    Understand, validate, and plan only.

LIVE_DEMO
    Produce an organizational Task and dispatch it through
    TradingRuntime to MT5 Demo.

Telegram never calls MT5Sender directly.
Telegram does not own Trading execution infrastructure.
"""

import asyncio
import json
from dataclasses import asdict, is_dataclass

import MetaTrader5 as mt5
from telethon import events

from backend.config import (
    MT5_BROKER_GOLD_SYMBOL,
    MT5_MAX_SPREAD_POINTS,
    TELEGRAM_EXECUTION_MODE,
    TELEGRAM_SIGNAL_GROUP_ID,
    validate_telegram_config,
)
from backend.integrations.telegram_client import client
from backend.integrations.telegram_task_execution_bridge import (
    TelegramTaskExecutionBridge,
)
from backend.integrations.telegram_task_producer import (
    TelegramTaskProducer,
)
from backend.integrations.telegram_trading_pipeline import (
    TelegramTradingPipeline,
)
from backend.trading.broker.mt5_client import MT5Client
from backend.trading.broker.mt5_safety import MT5Safety
from backend.trading.execution.live_execution_pipeline import (
    LiveExecutionPipeline,
)
from backend.trading.profile.trading_profile import (
    TradingProfile,
)
from backend.trading.runtime.trading_runtime import (
    TradingRuntime,
)
from backend.workers.telegram.telegram_receiver import (
    TelegramReceiver,
)


telegram_receiver = TelegramReceiver()

trading_profile = TradingProfile(
    profile_name="telegram_demo_gold",
    risk_percent=1.0,
    max_open_trades=1,
    allowed_symbols=("XAUUSD",),
    lot_policy_name="FIXED_001",
)

dry_run_pipeline = TelegramTradingPipeline(
    trading_profile
)

telegram_task_producer = TelegramTaskProducer(
    trading_profile
)

live_execution_pipeline = LiveExecutionPipeline(
    profile=trading_profile,
    symbol_map={
        "XAUUSD": MT5_BROKER_GOLD_SYMBOL,
    },
)

trading_runtime = TradingRuntime(
    execution_pipeline=(
        live_execution_pipeline
    )
)

task_execution_bridge = (
    TelegramTaskExecutionBridge(
        producer=telegram_task_producer,
        runtime=trading_runtime,
    )
)

mt5_client = MT5Client()

processed_message_keys: set[
    tuple[int, int]
] = set()


def to_serializable(value):
    if is_dataclass(value):
        return {
            key: to_serializable(item)
            for key, item in asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            str(key): to_serializable(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            to_serializable(item)
            for item in value
        ]

    return value


def print_result(
    title: str,
    result,
) -> None:
    print()
    print("===================================")
    print(title)
    print("===================================")

    print(
        json.dumps(
            to_serializable(result),
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    print("===================================")


def read_demo_decision_context() -> dict:
    """
    Read the minimum MT5 context required by DecisionGateway.

    This is an initial Demo capability, not the final
    market-knowledge or risk-management engine.
    """

    mt5.symbol_select(
        MT5_BROKER_GOLD_SYMBOL,
        True,
    )

    symbol_info = mt5.symbol_info(
        MT5_BROKER_GOLD_SYMBOL
    )

    tick = mt5.symbol_info_tick(
        MT5_BROKER_GOLD_SYMBOL
    )

    if symbol_info is None:
        raise RuntimeError(
            "Cannot read MT5 symbol information for "
            f"{MT5_BROKER_GOLD_SYMBOL}."
        )

    if tick is None:
        raise RuntimeError(
            "Cannot read MT5 tick for "
            f"{MT5_BROKER_GOLD_SYMBOL}."
        )

    point = symbol_info.point

    if point <= 0:
        raise RuntimeError(
            "MT5 symbol point must be greater than zero."
        )

    spread_points = (
        tick.ask - tick.bid
    ) / point

    positions = mt5.positions_get(
        symbol=MT5_BROKER_GOLD_SYMBOL
    )

    if positions is None:
        positions = ()

    market_open = (
        tick.bid > 0
        and tick.ask > 0
        and symbol_info.trade_mode
        != mt5.SYMBOL_TRADE_MODE_DISABLED
    )

    return {
        "has_open_position": (
            len(positions) > 0
        ),
        "spread_ok": (
            spread_points
            <= MT5_MAX_SPREAD_POINTS
        ),
        "market_open": market_open,

        # Demo capability only.
        # Final account-aware Risk Engine remains future work.
        "risk_ok": True,

        "spread_points": spread_points,
        "bid": tick.bid,
        "ask": tick.ask,
    }


@client.on(
    events.NewMessage(
        chats=TELEGRAM_SIGNAL_GROUP_ID
    )
)
async def new_message(event) -> None:
    source_key = (
        event.chat_id,
        event.id,
    )

    if source_key in processed_message_keys:
        print_result(
            "TODOBA DUPLICATE MESSAGE",
            {
                "status": "duplicate",
                "mode": TELEGRAM_EXECUTION_MODE,
                "chat_id": event.chat_id,
                "message_id": event.id,
            },
        )
        return

    try:
        incoming_signal = telegram_receiver.receive(
            message=event.raw_text,
            sender=(
                str(event.sender_id)
                if event.sender_id is not None
                else None
            ),
            sender_id=event.sender_id,
            chat_id=event.chat_id,
            message_id=event.id,
        )

        if TELEGRAM_EXECUTION_MODE == "DRY_RUN":
            result = dry_run_pipeline.process(
                incoming_signal
            )

            if (
                result.get("status")
                == "planned"
            ):
                processed_message_keys.add(
                    source_key
                )

            print_result(
                "TODOBA TELEGRAM DRY RUN",
                result,
            )

            return

        context = read_demo_decision_context()

        result = task_execution_bridge.execute(
            incoming_signal,
            has_open_position=(
                context["has_open_position"]
            ),
            spread_ok=context["spread_ok"],
            market_open=context["market_open"],
            risk_ok=context["risk_ok"],
        )

        if result.status == "executed":
            processed_message_keys.add(
                source_key
            )

        print_result(
            "TODOBA TELEGRAM LIVE DEMO",
            {
                "mode": "LIVE_DEMO",
                "chat_id": event.chat_id,
                "message_id": event.id,
                "market_context": context,
                "result": result,
            },
        )

    except Exception as error:
        print_result(
            "TODOBA TELEGRAM ERROR",
            {
                "status": "error",
                "mode": TELEGRAM_EXECUTION_MODE,
                "chat_id": event.chat_id,
                "message_id": event.id,
                "errors": [str(error)],
            },
        )


async def main() -> None:
    validate_telegram_config()

    print("Starting TODOBA Telegram Listener...")
    print(
        f"Watching Group ID: "
        f"{TELEGRAM_SIGNAL_GROUP_ID}"
    )
    print(
        f"Execution Mode: "
        f"{TELEGRAM_EXECUTION_MODE}"
    )

    if TELEGRAM_EXECUTION_MODE == "LIVE_DEMO":
        print(
            f"MT5 Broker Gold Symbol: "
            f"{MT5_BROKER_GOLD_SYMBOL}"
        )

        if not mt5_client.connect():
            raise RuntimeError(
                "TODOBA could not connect to MT5."
            )

        MT5Safety().validate()

        trading_runtime.start()

        account = mt5_client.get_account_info()

        if account is None:
            raise RuntimeError(
                "TODOBA could not read MT5 account."
            )

        print("MT5 Connection: READY")
        print(
            f"MT5 Account: "
            f"{account.login}"
        )
        print(
            f"MT5 Server: "
            f"{account.server}"
        )
        print("Trading Runtime: READY")

        print(
            "WARNING: LIVE_DEMO sends real orders "
            "to the currently connected MT5 account."
        )

    else:
        print("Live MT5 Orders: DISABLED")

    await client.start()

    print("Telegram Listener Running...")

    try:
        await client.run_until_disconnected()

    finally:
        if TELEGRAM_EXECUTION_MODE == "LIVE_DEMO":
            trading_runtime.stop()
            mt5_client.disconnect()

        if client.is_connected():
            await client.disconnect()

        print("Telegram Listener Stopped.")


if __name__ == "__main__":
    asyncio.run(main())