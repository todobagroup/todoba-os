"""
TODOBA Telegram Listener

Supports three explicit execution modes:

DRY_RUN
    Understand, validate, and plan only.

LIVE_DEMO
    Dispatch approved Tasks directly to local MT5 Demo.

REMOTE_VPS
    Submit approved execution missions to TODOBA Cloud.
    Trusted MQL5 Agents execute them remotely.

Telegram never calls MT5Sender directly.
Telegram does not manage broker execution lifecycle.
"""

import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from telethon import events

from backend.config import (
    MT5_BROKER_GOLD_SYMBOL,
    MT5_MAX_SPREAD_POINTS,
    TELEGRAM_EXECUTION_MODE,
    TELEGRAM_SIGNAL_GROUP_ID,
    TODOBA_CLOUD_BASE_URL,
    TODOBA_EXECUTOR_ID,
    TODOBA_EXECUTOR_SECRET,
    TODOBA_TRUSTED_AGENT_ID,
    validate_telegram_config,
)
from backend.integrations.telegram_client import (
    create_telegram_client,
)
from backend.integrations.telegram_task_producer import (
    TelegramTaskProducer,
)
from backend.integrations.telegram_trading_pipeline import (
    TelegramTradingPipeline,
)
from backend.trading.execution.execution_planner import (
    create_plan,
)
from backend.trading.execution.remote_execution_mission_http_client import (
    RemoteExecutionMissionHttpClient,
)
from backend.trading.execution.trade_task_execution_mission_adapter import (
    TradeTaskExecutionMissionAdapter,
)
from backend.trading.profile.trading_profile import (
    TradingProfile,
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

remote_profile = None
remote_task_producer = None
remote_mission_adapter = None
remote_http_client = None


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

    remote_profile = TradingProfile(
        profile_name="telegram_demo_gold",
        risk_percent=1.0,
        max_open_trades=10,
        allowed_symbols=("XAUUSD",),
        lot_policy_name="FIXED_001",
    )

    remote_task_producer = TelegramTaskProducer(
        remote_profile
    )

    remote_mission_adapter = (
        TradeTaskExecutionMissionAdapter()
    )

    remote_http_client = (
        RemoteExecutionMissionHttpClient(
            cloud_base_url=TODOBA_CLOUD_BASE_URL,
            executor_id=TODOBA_EXECUTOR_ID,
            executor_secret=TODOBA_EXECUTOR_SECRET,
        )
    )

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

def _to_utc_iso8601(
    value: datetime,
) -> str:
    return (
        value.astimezone(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def process_remote_vps_signal(
    incoming_signal: IncomingSignal,
) -> dict:
    if not isinstance(
        incoming_signal,
        IncomingSignal,
    ):
        raise TypeError(
            "process_remote_vps_signal requires "
            "IncomingSignal."
        )

    source_key = incoming_signal.source_key()

    if source_key is None:
        raise ValueError(
            "REMOTE_VPS signal requires "
            "chat_id and message_id."
        )

    if source_key in processed_message_keys:
        return {
            "status": "duplicate",
            "source_key": source_key,
        }

    if (
        remote_profile is None
        or remote_task_producer is None
        or remote_mission_adapter is None
        or remote_http_client is None
    ):
        raise RuntimeError(
            "REMOTE_VPS composition is not available."
        )

    broker_state = (
        remote_http_client.read_latest_broker_state(
            agent_id=TODOBA_TRUSTED_AGENT_ID
        )
    )

    production = remote_task_producer.produce(
        incoming_signal,
        open_position_count=int(
            broker_state["open_position_count"]
        ),
        spread_ok=(
            float(broker_state["spread_points"])
            <= MT5_MAX_SPREAD_POINTS
        ),
        market_open=(
            float(broker_state["bid"]) > 0
            and float(broker_state["ask"]) > 0
        ),
        risk_ok=True,
    )

    if production.task is None:
        return {
            "status": production.status,
            "production": production,
            "broker_state": broker_state,
        }

    if production.signal is None:
        raise RuntimeError(
            "Approved Telegram production "
            "does not contain a signal."
        )

    execution_plan = create_plan(
        production.signal,
        remote_profile,
    )

    created_at = datetime.now(
        UTC
    )

    expires_at = (
        created_at
        + timedelta(minutes=2)
    )

    chat_id, message_id = source_key

    if message_id <= 0:
        raise ValueError(
            "Telegram message_id must be positive."
        )

    mission = remote_mission_adapter.to_mission(
        production.task,
        mission_id=(
            f"telegram-{abs(chat_id)}-{message_id}"
        ),
        agent_id=TODOBA_TRUSTED_AGENT_ID,
        account_fingerprint=str(
            broker_state["account_fingerprint"]
        ),
        volume=execution_plan.lot,
        magic_number=execution_plan.magic_number,
        comment=execution_plan.comment,
        created_at=_to_utc_iso8601(
            created_at
        ),
        expires_at=_to_utc_iso8601(
            expires_at
        ),
        sequence=message_id,
    )

    cloud_response = remote_http_client.send(
        mission
    )

    processed_message_keys.add(
        source_key
    )

    return {
        "status": "submitted",
        "production": production,
        "broker_state": broker_state,
        "mission": mission,
        "cloud_response": cloud_response,
    }
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
                result = dry_run_pipeline.process(
                    incoming_signal
                )

                print_result(
                    "TODOBA TELEGRAM DRY RUN",
                    result,
                )

                return

            if TELEGRAM_EXECUTION_MODE == "REMOTE_VPS":
                result = process_remote_vps_signal(
                    incoming_signal
                )

                print_result(
                    "TODOBA TELEGRAM REMOTE VPS",
                    {
                        "mode": "REMOTE_VPS",
                        "result": result,
                    },
                )

                return

            context = read_demo_decision_context()

            result = task_execution_bridge.execute(
                incoming_signal,
                open_position_count=(
                    context["open_position_count"]
                ),
                spread_ok=context["spread_ok"],
                market_open=context["market_open"],
                risk_ok=context["risk_ok"],
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

        elif TELEGRAM_EXECUTION_MODE == "REMOTE_VPS":
            print("Local MT5 Orders: DISABLED")
            print("Remote VPS Execution: ENABLED")

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