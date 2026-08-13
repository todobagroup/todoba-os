"""
TODOBA Telegram Remote VPS Mission Flow Tests

Proof:

Approved Telegram trade Task
->
TradeTaskRemoteExecutionBridge
->
ExecutionMissionService
->
ExecutionMissionStore
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.integrations.telegram_task_producer import (
    TelegramTaskProducer,
)
from backend.task.task import Task
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_service import (
    ExecutionMissionService,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.trade_task_remote_execution_bridge import (
    TradeTaskRemoteExecutionBridge,
)
from backend.trading.profile.trading_profile import (
    TradingProfile,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)


def test_telegram_signal_becomes_remote_execution_mission(
    tmp_path,
):
    profile = TradingProfile(
        profile_name="remote_vps_test",
        risk_percent=1.0,
        max_open_trades=10,
        allowed_symbols=("XAUUSD",),
        lot_policy_name="FIXED_001",
    )

    producer = TelegramTaskProducer(
        profile
    )

    incoming_signal = IncomingSignal(
        source="telegram",
        message=(
            "Sell GOLD NOW\n"
            "SL: 4334\n"
            "TP: 4303"
        ),
        sender="test",
        sender_id=1,
        chat_id=2,
        message_id=3,
        received_at=datetime.now(
            UTC
        ),
    )

    production = producer.produce(
        incoming_signal,
        open_position_count=0,
        spread_ok=True,
        market_open=True,
        risk_ok=True,
    )

    assert production.status == "task_created"

    assert isinstance(
        production.task,
        Task,
    )

    repository = ExecutionMissionRepository()

    persistence = ExecutionMissionPersistence(
        tmp_path / "execution_missions.json"
    )

    store = ExecutionMissionStore()

    delivery_bridge = ExecutionMissionDeliveryBridge(
        store
    )

    registry = ExecutionMissionRegistry()

    record_persistence = (
        ExecutionMissionRecordPersistence(
            tmp_path
            / "execution_mission_records.json"
        )
    )

    service = ExecutionMissionService(
        repository,
        persistence,
        delivery_bridge,
        registry,
        record_persistence,
    )

    remote_bridge = TradeTaskRemoteExecutionBridge(
        mission_service=service,
    )

    mission = remote_bridge.dispatch(
        production.task,
        mission_id="proof089-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        volume=0.01,
        magic_number=10001,
        comment="TODOBA proof089",
        created_at="2026-08-10T00:00:00Z",
        expires_at="2026-08-10T00:02:00Z",
        sequence=89,
    )

    assert mission.order_type == "SELL NOW"
    assert mission.symbol == "XAUUSD"
    assert mission.entry is None
    assert mission.sl == 4334.0
    assert mission.tp == 4303.0

    assert repository.size() == 1
    assert registry.size() == 1
    assert store.size() == 1