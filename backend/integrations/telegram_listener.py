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
from pathlib import Path
from datetime import timedelta

from telethon import events

from backend.config import (
    MT5_BROKER_GOLD_SYMBOL,
    MT5_MAX_SPREAD_POINTS,
    TELEGRAM_AUTHORIZED_SENDER_IDS,
    TELEGRAM_EXECUTION_MODE,
    TELEGRAM_SIGNAL_GROUP_ID,
    TODOBA_CLOUD_BASE_URL,
    TODOBA_CONTROL_PLANE_DATA_ROOT,
    TODOBA_EXECUTOR_ID,
    TODOBA_EXECUTOR_SECRET,
    validate_telegram_config,
)
from backend.commercial.customer_deployment_execution_target_projection import (
    CustomerDeploymentExecutionTargetProjection,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)

from backend.integrations.telegram_client import (
    create_telegram_client,
)

from backend.integrations.telegram_dispatch_progress_store import (
    TelegramDispatchProgressStore,
    TelegramDispatchStatus,
)
from backend.integrations.telegram_dispatch_recovery import (
    TelegramDispatchRecovery,
)

from backend.integrations.telegram_sender_authorizer import (
    TelegramSenderAuthorizer,
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

from backend.trading.execution.execution_target_registry import (
    ExecutionTargetRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
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
from backend.trading.risk.position_sizing_engine import (
    PositionSizingEngine,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)
from backend.workers.telegram.telegram_receiver import (
    TelegramReceiver,
)


telegram_receiver = TelegramReceiver()

telegram_sender_authorizer = (
    TelegramSenderAuthorizer(
        authorized_sender_ids=(
            TELEGRAM_AUTHORIZED_SENDER_IDS
        ),
    )
)

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
remote_execution_target_registry = None
remote_dispatch_progress_store = None
remote_dispatch_recovery = None

BROKER_STATE_MAX_AGE_SECONDS = 30.0

CUSTOMER_DEPLOYMENT_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_deployments.json"
)

TRUSTED_AGENT_ACCOUNT_BINDING_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "trading"
    / "trusted_agent_account_bindings.json"
)

TELEGRAM_DISPATCH_PROGRESS_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "telegram_dispatch_progress.json"
)


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

    remote_execution_target_registry = (
        ExecutionTargetRegistry()
    )

    remote_dispatch_progress_store = (
        TelegramDispatchProgressStore(
            storage_path=(
                TELEGRAM_DISPATCH_PROGRESS_STORAGE_PATH
            )
        )
    )

    remote_dispatch_recovery = (
        TelegramDispatchRecovery(
            progress_store=(
                remote_dispatch_progress_store
            ),
            execution_target_registry=(
                remote_execution_target_registry
            ),
            http_client=remote_http_client,
        )
    )

def refresh_remote_execution_targets() -> int:
    """
    Refresh routing targets from durable commercial truth.

    Durable source registries are reconstructed on each
    refresh so changes persisted by another process become
    visible without reloading this module.

    The runtime ExecutionTargetRegistry object is retained
    so dispatch recovery and live fan-out continue sharing
    the same registry reference.
    """

    if TELEGRAM_EXECUTION_MODE != "REMOTE_VPS":
        return 0

    if remote_execution_target_registry is None:
        raise RuntimeError(
            "REMOTE_VPS execution target registry "
            "is not available."
        )

    deployment_registry = CustomerDeploymentRegistry(
        CUSTOMER_DEPLOYMENT_STORAGE_PATH
    )

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            TRUSTED_AGENT_ACCOUNT_BINDING_STORAGE_PATH
        )
    )

    projection = (
        CustomerDeploymentExecutionTargetProjection(
            deployment_registry=deployment_registry,
            account_binding_store=(
                account_binding_store
            ),
            execution_target_registry=(
                remote_execution_target_registry
            ),
        )
    )

    projected_count = projection.project()

    if projected_count <= 0:
        raise RuntimeError(
            "REMOTE_VPS commercial execution "
            "target fleet is empty."
        )

    return projected_count


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


def _broker_state_rejection_reason(
    broker_state: dict,
    *,
    now: datetime | None = None,
) -> str | None:
    received_at_value = broker_state.get(
        "received_at"
    )

    if received_at_value is None:
        return (
            "Broker state received_at "
            "is required."
        )

    if not isinstance(
        received_at_value,
        str,
    ):
        return (
            "Broker state received_at "
            "is invalid."
        )

    normalized_received_at = (
        received_at_value.strip()
    )

    if not normalized_received_at:
        return (
            "Broker state received_at "
            "is invalid."
        )

    if normalized_received_at.endswith(
        "Z"
    ):
        normalized_received_at = (
            normalized_received_at[:-1]
            + "+00:00"
        )

    try:
        received_at = datetime.fromisoformat(
            normalized_received_at
        )
    except ValueError:
        return (
            "Broker state received_at "
            "is invalid."
        )

    if received_at.tzinfo is None:
        return (
            "Broker state received_at "
            "is invalid."
        )

    current_time = (
        datetime.now(
            UTC
        )
        if now is None
        else now.astimezone(
            UTC
        )
    )

    state_age_seconds = (
        current_time
        - received_at.astimezone(
            UTC
        )
    ).total_seconds()

    if (
        state_age_seconds
        > BROKER_STATE_MAX_AGE_SECONDS
    ):
        return "Broker state is stale."

    return None

def _dispatch_mission_is_expired(
    mission,
    *,
    now: datetime | None = None,
) -> bool:
    expires_at_value = mission.expires_at

    if not isinstance(
        expires_at_value,
        str,
    ):
        raise RuntimeError(
            "Persisted Telegram dispatch mission "
            "expires_at is invalid."
        )

    normalized_expires_at = (
        expires_at_value.strip()
    )

    if not normalized_expires_at:
        raise RuntimeError(
            "Persisted Telegram dispatch mission "
            "expires_at is invalid."
        )

    if normalized_expires_at.endswith("Z"):
        normalized_expires_at = (
            normalized_expires_at[:-1]
            + "+00:00"
        )

    try:
        expires_at = datetime.fromisoformat(
            normalized_expires_at
        )
    except ValueError as error:
        raise RuntimeError(
            "Persisted Telegram dispatch mission "
            "expires_at is invalid."
        ) from error

    if expires_at.tzinfo is None:
        raise RuntimeError(
            "Persisted Telegram dispatch mission "
            "expires_at is invalid."
        )

    current_time = (
        datetime.now(UTC)
        if now is None
        else now.astimezone(UTC)
    )

    return (
        current_time
        >= expires_at.astimezone(UTC)
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

    if not telegram_sender_authorizer.is_authorized(
        incoming_signal.sender_id
    ):
        return {
            "status": "unauthorized_sender",
            "sender_id": incoming_signal.sender_id,
        }

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

    chat_id, message_id = source_key

    if message_id <= 0:
        raise ValueError(
            "Telegram message_id must be positive."
        )

    refresh_remote_execution_targets()

    if remote_execution_target_registry is not None:
        if remote_dispatch_progress_store is None:
            raise RuntimeError(
                "REMOTE_VPS dispatch progress store "
                "is not available."
            )

        targets = (
            remote_execution_target_registry.all()
        )

        if not targets:
            raise RuntimeError(
                "REMOTE_VPS execution target registry "
                "is empty."
            )

        target_results: list[dict] = []

        for target in targets:
            existing_progress = (
                remote_dispatch_progress_store.get(
                    chat_id=chat_id,
                    message_id=message_id,
                    agent_id=target.agent_id,
                )
            )

            if existing_progress is not None:
                persisted_mission = (
                    existing_progress.mission
                )

                if (
                    persisted_mission.agent_id
                    != target.agent_id
                    or persisted_mission.account_fingerprint
                    != target.account_fingerprint
                ):
                    raise RuntimeError(
                        "Persisted Telegram dispatch "
                        "mission does not match "
                        "execution target."
                    )

                if (
                    existing_progress.status
                    == TelegramDispatchStatus.SUBMITTED
                ):
                    target_results.append(
                        {
                            "agent_id": target.agent_id,
                            "status": "submitted",
                            "mission": persisted_mission,
                            "cloud_response": None,
                            "recovered": True,
                        }
                    )
                    continue

                if (
                    existing_progress.status
                    == TelegramDispatchStatus.EXPIRED
                ):
                    target_results.append(
                        {
                            "agent_id": target.agent_id,
                            "status": "expired",
                            "mission": persisted_mission,
                        }
                    )
                    continue

                if _dispatch_mission_is_expired(
                    persisted_mission
                ):
                    remote_dispatch_progress_store.mark_expired(
                        chat_id=chat_id,
                        message_id=message_id,
                        agent_id=target.agent_id,
                    )

                    target_results.append(
                        {
                            "agent_id": target.agent_id,
                            "status": "expired",
                            "mission": persisted_mission,
                        }
                    )
                    continue

                try:
                    cloud_response = (
                        remote_http_client.send(
                            persisted_mission
                        )
                    )
                except Exception as error:
                    target_results.append(
                        {
                            "agent_id": target.agent_id,
                            "status": "transport_failed",
                            "operation": "send_mission",
                            "reason": str(error),
                            "mission": persisted_mission,
                        }
                    )
                    continue

                remote_dispatch_progress_store.mark_submitted(
                    chat_id=chat_id,
                    message_id=message_id,
                    agent_id=target.agent_id,
                )

                target_results.append(
                    {
                        "agent_id": target.agent_id,
                        "status": "submitted",
                        "mission": persisted_mission,
                        "cloud_response": cloud_response,
                        "recovered": True,
                    }
                )
                continue

            try:
                broker_state = (
                    remote_http_client
                    .read_latest_broker_state(
                        agent_id=target.agent_id
                    )
                )
            except Exception as error:
                target_results.append(
                    {
                        "agent_id": target.agent_id,
                        "status": "transport_failed",
                        "operation": "read_broker_state",
                        "reason": str(error),
                    }
                )
                continue

            rejection_reason = (
                _broker_state_rejection_reason(
                    broker_state
                )
            )

            if rejection_reason is not None:
                target_results.append(
                    {
                        "agent_id": target.agent_id,
                        "status": (
                            "broker_state_rejected"
                        ),
                        "reason": rejection_reason,
                        "broker_state": broker_state,
                    }
                )
                continue

            if (
                str(
                    broker_state.get(
                        "agent_id",
                        "",
                    )
                ).strip()
                != target.agent_id
            ):
                target_results.append(
                    {
                        "agent_id": target.agent_id,
                        "status": (
                            "broker_state_rejected"
                        ),
                        "reason": (
                            "Broker state Agent does not "
                            "match execution target."
                        ),
                        "broker_state": broker_state,
                    }
                )
                continue

            if (
                str(
                    broker_state.get(
                        "account_fingerprint",
                        "",
                    )
                ).strip()
                != target.account_fingerprint
            ):
                target_results.append(
                    {
                        "agent_id": target.agent_id,
                        "status": (
                            "broker_state_rejected"
                        ),
                        "reason": (
                            "Broker state account_fingerprint "
                            "does not match execution target."
                        ),
                        "broker_state": broker_state,
                    }
                )
                continue

            production = (
                remote_task_producer.produce(
                    incoming_signal,
                    open_position_count=int(
                        broker_state[
                            "open_position_count"
                        ]
                    ),
                    pending_order_count=int(
                        broker_state[
                            "pending_order_count"
                        ]
                    ),
                    spread_ok=(
                        float(
                            broker_state[
                                "spread_points"
                            ]
                        )
                        <= MT5_MAX_SPREAD_POINTS
                    ),
                    market_open=(
                        float(
                            broker_state["bid"]
                        )
                        > 0
                        and float(
                            broker_state["ask"]
                        )
                        > 0
                    ),
                    risk_ok=True,
                )
            )

            if production.task is None:
                target_results.append(
                    {
                        "agent_id": target.agent_id,
                        "status": production.status,
                        "production": production,
                        "broker_state": broker_state,
                    }
                )
                continue

            if production.signal is None:
                raise RuntimeError(
                    "Approved Telegram production "
                    "does not contain a signal."
                )

            execution_plan = create_plan(
                production.signal,
                remote_profile,
            )

            sizing_result = (
                PositionSizingEngine().evaluate(
                    account_equity=float(
                        broker_state["equity"]
                    ),
                )
            )

            if not sizing_result.approved:
                target_results.append(
                    {
                        "agent_id": target.agent_id,
                        "status": "sizing_rejected",
                        "reason": sizing_result.reason,
                        "production": production,
                        "broker_state": broker_state,
                    }
                )
                continue

            created_at = datetime.now(
                UTC
            )

            expires_at = (
                created_at
                + timedelta(minutes=2)
            )

            mission = (
                remote_mission_adapter.to_mission(
                    production.task,
                    mission_id=(
                        f"telegram-{abs(chat_id)}-"
                        f"{message_id}-"
                        f"{target.agent_id}"
                    ),
                    agent_id=target.agent_id,
                    account_fingerprint=(
                        target.account_fingerprint
                    ),
                    volume=sizing_result.volume,
                    magic_number=(
                        execution_plan.magic_number
                    ),
                    comment=execution_plan.comment,
                    created_at=_to_utc_iso8601(
                        created_at
                    ),
                    expires_at=_to_utc_iso8601(
                        expires_at
                    ),
                    sequence=message_id,
                )
            )

            prepared_progress = (
                remote_dispatch_progress_store.prepare(
                    chat_id=chat_id,
                    message_id=message_id,
                    mission=mission,
                )
            )

            try:
                cloud_response = (
                    remote_http_client.send(
                        prepared_progress.mission
                    )
                )
            except Exception as error:
                target_results.append(
                    {
                        "agent_id": target.agent_id,
                        "status": "transport_failed",
                        "operation": "send_mission",
                        "reason": str(error),
                        "mission": (
                            prepared_progress.mission
                        ),
                    }
                )
                continue

            remote_dispatch_progress_store.mark_submitted(
                chat_id=chat_id,
                message_id=message_id,
                agent_id=target.agent_id,
            )

            target_results.append(
                {
                    "agent_id": target.agent_id,
                    "status": "submitted",
                    "production": production,
                    "broker_state": broker_state,
                    "mission": (
                        prepared_progress.mission
                    ),
                    "cloud_response": cloud_response,
                }
            )

        submitted_count = sum(
            1
            for result in target_results
            if result["status"] == "submitted"
        )

        if submitted_count == len(
            target_results
        ):
            overall_status = "submitted"
        elif submitted_count > 0:
            overall_status = (
                "partially_submitted"
            )
        else:
            overall_status = "rejected"

        processed_message_keys.add(
            source_key
        )

        return {
            "status": overall_status,
            "target_results": target_results,
        }

    raise RuntimeError(
        "REMOTE_VPS execution target registry "
        "is not available."
    )


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

    pending_orders = mt5.orders_get(
        symbol=MT5_BROKER_GOLD_SYMBOL
    )

    if pending_orders is None:
        raise RuntimeError(
            "Cannot read MT5 pending orders."
        )

    return {
        "open_position_count": len(
            positions
        ),
        "pending_order_count": len(
            pending_orders
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

            if not telegram_sender_authorizer.is_authorized(
                incoming_signal.sender_id
            ):
                print_result(
                    "TODOBA TELEGRAM UNAUTHORIZED",
                    {
                        "status": "unauthorized_sender",
                        "sender_id": (
                            incoming_signal.sender_id
                        ),
                    },
                )

                return

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

    if TELEGRAM_EXECUTION_MODE == "REMOTE_VPS":
        refresh_remote_execution_targets()

        if remote_dispatch_recovery is None:
            raise RuntimeError(
                "REMOTE_VPS dispatch recovery "
                "is not available."
            )

        remote_dispatch_recovery.restore()

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