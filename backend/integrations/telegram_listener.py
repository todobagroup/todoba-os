"""
TODOBA Telegram Listener

Supports two explicit execution modes:

DRY_RUN
    Understand, validate, and plan only.

LIVE_DEMO
    Produce an organizational Task and dispatch it through
    the Trading Department to MT5 Demo.

Telegram never calls MT5Sender directly.
Telegram does not construct or manage Trading lifecycle.
"""

import asyncio
import json
from dataclasses import asdict, is_dataclass

from telethon import events

from backend.config import (
    MT5_BROKER_GOLD_SYMBOL,
    MT5_MAX_SPREAD_POINTS,
    TELEGRAM_EXECUTION_MODE,
    TELEGRAM_SIGNAL_GROUP_ID,
    validate_telegram_config,
)
from backend.integrations.telegram_client import (
    create_telegram_client,
)
from backend.integrations.telegram_trading_pipeline import (
    TelegramTradingPipeline,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)
from backend.workers.telegram.telegram_receiver import (
    TelegramReceiver,
)


telegram_receiver = TelegramReceiver()

client = None

runtime_bootstrap = None
runtime = None
trading_profile = None
task_execution_bridge = None
mt5 = None


if TELEGRAM_EXECUTION_MODE != "REMOTE_VPS":
    import MetaTrader5 as mt5_module

    from backend.runtime.runtime_bootstrap import (
        RuntimeBootstrap,
    )

    runtime_bootstrap = RuntimeBootstrap()
    runtime = runtime_bootstrap.create_runtime()

    trading_profile = runtime_bootstrap.profile

    task_execution_bridge = (
        runtime_bootstrap.task_execution_bridge
    )

    mt5 = mt5_module

    dry_run_pipeline = TelegramTradingPipeline(
        trading_profile
    )

else:
    dry_run_pipeline = None


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
            "Cannot read MT5 symbol information."
        )

    if tick is None:
        raise RuntimeError(
            "Cannot read MT5 tick."
        )

    point = symbol_info.point

    spread_points = (
        tick.ask - tick.bid
    ) / point

    positions = mt5.positions_get(
        symbol=MT5_BROKER_GOLD_SYMBOL
    )

    if positions is None:
        raise RuntimeError(
            "Cannot read MT5 positions."
        )

    return {
        "open_position_count": len(
            positions
        ),
        "max_open_trades": (
            trading_profile.max_open_trades
        ),
        "spread_ok": (
            spread_points
            <= MT5_MAX_SPREAD_POINTS
        ),
        "market_open": (
            tick.bid > 0
            and tick.ask > 0
        ),
        "risk_ok": True,
        "spread_points": spread_points,
        "bid": tick.bid,
        "ask": tick.ask,
    }


async def register_handlers() -> None:
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
            return

        try:
            incoming_signal = (
                telegram_receiver.receive(
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
            )

            if TELEGRAM_EXECUTION_MODE == "DRY_RUN":
                result = (
                    dry_run_pipeline.process(
                        incoming_signal
                    )
                )

                print_result(
                    "TODOBA TELEGRAM DRY RUN",
                    result,
                )

                return

            context = read_demo_decision_context()

            result = (
                task_execution_bridge.execute(
                    incoming_signal,
                    open_position_count=(
                        context["open_position_count"]
                    ),
                    spread_ok=context["spread_ok"],
                    market_open=context["market_open"],
                    risk_ok=context["risk_ok"],
                )
            )

            print_result(
                "TODOBA TELEGRAM LIVE DEMO",
                {
                    "mode": "LIVE_DEMO",
                    "market_context": context,
                    "result": result,
                },
            )

        except Exception as error:
            print_result(
                "TODOBA TELEGRAM ERROR",
                {
                    "error": str(error),
                },
            )


async def main() -> None:
    global client

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

    runtime_started = False

    try:
        if TELEGRAM_EXECUTION_MODE == "LIVE_DEMO":
            await runtime.start()
            runtime_started = True

            print(
                "WARNING: LIVE_DEMO sends real orders "
                "to the currently connected MT5 account."
            )

        else:
            print("Live MT5 Orders: DISABLED")

        client = create_telegram_client()

        await register_handlers()

        await client.start()

        print("Telegram Listener Running...")

        await client.run_until_disconnected()

    finally:
        if client is not None:
            if client.is_connected():
                await client.disconnect()

        if runtime_started:
            await runtime.stop()

        print("Telegram Listener Stopped.")


if __name__ == "__main__":
    asyncio.run(main())