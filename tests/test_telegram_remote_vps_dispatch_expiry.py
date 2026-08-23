"""
TODOBA Telegram Remote VPS Durable Dispatch Expiry Tests

Proof:

A persisted PENDING mission that has already expired:
- must not read Broker State again
- must not be rebuilt
- must not be position-sized again
- must not be sent to Cloud
- must become durably EXPIRED
"""

import importlib
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.integrations.telegram_dispatch_progress_store import (
    TelegramDispatchProgressStore,
    TelegramDispatchStatus,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)








def configure_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = {
        "TELEGRAM_API_ID": "1",
        "TELEGRAM_API_HASH": "test-hash",
        "TELEGRAM_SESSION": "test-session",
        "TELEGRAM_SIGNAL_GROUP_ID": "-1001",
        "TELEGRAM_EXECUTION_MODE": "REMOTE_VPS",
        "TELEGRAM_AUTHORIZED_SENDER_IDS": "1",
        "MT5_MAX_SPREAD_POINTS": "100",
        "TODOBA_CLOUD_BASE_URL": (
            "https://api.todobagroup.com"
        ),
        "TODOBA_EXECUTOR_ID": (
            "telegram-executor-expiry"
        ),
        "TODOBA_EXECUTOR_SECRET": (
            "expiry-executor-secret"
        ),
        "TODOBA_TRUSTED_AGENT_ID": "",
        "TODOBA_TRUSTED_AGENTS_JSON": "",
        "TODOBA_EXECUTION_TARGETS_JSON": "",
    }

    for name, value in environment.items():
        monkeypatch.setenv(
            name,
            value,
        )


def load_listener(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
):
    commercial_executor_fleet(
        (
            (
                "trusted-agent-001",
                "account-a",
            ),
        )
    )

    monkeypatch.chdir(
        tmp_path
    )

    configure_environment(
        monkeypatch
    )

    import backend.config as config

    importlib.reload(
        config
    )

    sys.modules.pop(
        "backend.integrations.telegram_listener",
        None,
    )

    return importlib.import_module(
        "backend.integrations.telegram_listener"
    )


def make_incoming_signal() -> IncomingSignal:
    return IncomingSignal(
        source="telegram",
        message=(
            "Sell GOLD NOW\n"
            "SL: 4380\n"
            "TP: 4340"
        ),
        sender="dispatch-expiry-proof",
        sender_id=1,
        chat_id=-1001,
        message_id=168501,
        received_at=datetime.now(
            UTC
        ),
    )


def make_expired_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=(
            "telegram-1001-168501-"
            "trusted-agent-001"
        ),
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        symbol="XAUUSD",
        order_type="SELL NOW",
        volume=0.01,
        entry=None,
        sl=4380.0,
        tp=4340.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-08-20T00:00:00Z",
        expires_at="2026-08-20T00:02:00Z",
        sequence=168501,
        security_sequence=0,
    )


class FailIfHttpRuns:
    def read_latest_broker_state(
        self,
        *,
        agent_id: str,
    ) -> dict:
        raise AssertionError(
            "Expired retry must not read Broker State."
        )

    def send(
        self,
        mission,
    ) -> dict:
        raise AssertionError(
            "Expired retry must not send mission."
        )


class FailIfSizingRuns:
    def evaluate(
        self,
        *,
        account_equity: float,
    ):
        raise AssertionError(
            "Expired retry must not recalculate "
            "position size."
        )


def test_expired_pending_mission_is_not_sent_and_becomes_durably_expired(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
        commercial_executor_fleet,
    )

    progress_store = (
        listener.remote_dispatch_progress_store
    )

    assert isinstance(
        progress_store,
        TelegramDispatchProgressStore,
    )

    expired_mission = (
        make_expired_mission()
    )

    prepared = progress_store.prepare(
        chat_id=-1001,
        message_id=168501,
        mission=expired_mission,
    )

    assert prepared.status == (
        TelegramDispatchStatus.PENDING
    )

    monkeypatch.setattr(
        listener,
        "remote_http_client",
        FailIfHttpRuns(),
        raising=False,
    )

    monkeypatch.setattr(
        listener,
        "PositionSizingEngine",
        FailIfSizingRuns,
    )

    listener.processed_message_keys.clear()

    result = (
        listener.process_remote_vps_signal(
            make_incoming_signal()
        )
    )

    assert result["status"] == (
        "rejected"
    )

    assert len(
        result["target_results"]
    ) == 1

    target_result = (
        result["target_results"][0]
    )

    assert target_result["agent_id"] == (
        "trusted-agent-001"
    )

    assert target_result["status"] == (
        "expired"
    )

    assert (
        target_result["mission"]
        == expired_mission
    )

    progress = progress_store.get(
        chat_id=-1001,
        message_id=168501,
        agent_id="trusted-agent-001",
    )

    assert progress is not None

    assert progress.status == (
        TelegramDispatchStatus.EXPIRED
    )

    assert progress.mission == (
        expired_mission
    )

    restored_store = (
        TelegramDispatchProgressStore(
            storage_path=(
                tmp_path
                / "data"
                / "trading"
                / "telegram_dispatch_progress.json"
            )
        )
    )

    restored = restored_store.get(
        chat_id=-1001,
        message_id=168501,
        agent_id="trusted-agent-001",
    )

    assert restored is not None

    assert restored.status == (
        TelegramDispatchStatus.EXPIRED
    )

    assert restored.mission == (
        expired_mission
    )