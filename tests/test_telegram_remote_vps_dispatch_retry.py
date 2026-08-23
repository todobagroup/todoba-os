"""
TODOBA Telegram Remote VPS Durable Dispatch Retry Tests

Proof:

First attempt:
- Target A is submitted successfully.
- Target B reaches HTTP dispatch but times out.
- Target A becomes SUBMITTED.
- Target B remains PENDING with the exact mission persisted.

After executor restart:
- Target A is not sent again.
- Target B is retried with the exact persisted mission.
- Broker State is not read again.
- Position sizing is not recalculated.
- No new timestamps or payload are generated.
"""

import importlib
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.integrations.telegram_dispatch_progress_store import (
    TelegramDispatchProgressStore,
    TelegramDispatchStatus,
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
            "telegram-executor-retry"
        ),
        "TODOBA_EXECUTOR_SECRET": (
            "retry-executor-secret"
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
    commercial_executor_fleet,
):
    commercial_executor_fleet(
        (
            (
                "trusted-agent-001",
                "account-a",
            ),
            (
                "trusted-agent-002",
                "account-b",
            ),
        )
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


def make_broker_state(
    *,
    agent_id: str,
    account_fingerprint: str,
    equity: float,
) -> dict:
    return {
        "status": "available",
        "received_at": (
            datetime.now(
                UTC
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        ),
        "agent_id": agent_id,
        "account_fingerprint": (
            account_fingerprint
        ),
        "equity": equity,
        "open_position_count": 0,
        "pending_order_count": 0,
        "symbol": "XAUUSD",
        "bid": 4365.83,
        "ask": 4366.08,
        "spread_points": 25.0,
    }


def make_incoming_signal() -> IncomingSignal:
    return IncomingSignal(
        source="telegram",
        message=(
            "Sell GOLD NOW\n"
            "SL: 4380\n"
            "TP: 4340"
        ),
        sender="dispatch-retry-proof",
        sender_id=1,
        chat_id=-1001,
        message_id=168401,
        received_at=datetime.now(
            UTC
        ),
    )


class FakePositionSizingEngine:
    def evaluate(
        self,
        *,
        account_equity: float,
    ):
        volumes = {
            1000.0: 0.01,
            2000.0: 0.02,
        }

        return SimpleNamespace(
            approved=True,
            volume=volumes[
                account_equity
            ],
            reason="approved",
        )


class FirstAttemptHttpClient:
    """
    Target A succeeds.

    Target B reaches Cloud dispatch but the client sees
    an ambiguous timeout.
    """

    def __init__(self) -> None:
        self.read_agent_ids: list[str] = []
        self.sent_missions = []

        self.states = {
            "trusted-agent-001": (
                make_broker_state(
                    agent_id=(
                        "trusted-agent-001"
                    ),
                    account_fingerprint=(
                        "account-a"
                    ),
                    equity=1000.0,
                )
            ),
            "trusted-agent-002": (
                make_broker_state(
                    agent_id=(
                        "trusted-agent-002"
                    ),
                    account_fingerprint=(
                        "account-b"
                    ),
                    equity=2000.0,
                )
            ),
        }

    def read_latest_broker_state(
        self,
        *,
        agent_id: str,
    ) -> dict:
        self.read_agent_ids.append(
            agent_id
        )

        return self.states[
            agent_id
        ]

    def send(
        self,
        mission,
    ) -> dict:
        self.sent_missions.append(
            mission
        )

        if (
            mission.agent_id
            == "trusted-agent-002"
        ):
            raise httpx.ReadTimeout(
                "Ambiguous dispatch timeout."
            )

        return {
            "status": "persisted",
            "mission_id": mission.mission_id,
        }


class RetryOnlyHttpClient:
    """
    Retry must use persisted missions only.

    Any Broker State read means the retry incorrectly
    rebuilt execution state.
    """

    def __init__(self) -> None:
        self.sent_missions = []

    def read_latest_broker_state(
        self,
        *,
        agent_id: str,
    ) -> dict:
        raise AssertionError(
            "Retry must not read Broker State."
        )

    def send(
        self,
        mission,
    ) -> dict:
        self.sent_missions.append(
            mission
        )

        return {
            "status": "persisted",
            "mission_id": mission.mission_id,
        }


class FailIfSizingEngineRuns:
    """
    Sizing must never run for a persisted retry mission.
    """

    def evaluate(
        self,
        *,
        account_equity: float,
    ):
        raise AssertionError(
            "Retry must not recalculate position size."
        )


def test_restart_retries_only_pending_target_with_exact_persisted_mission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
) -> None:
    storage_path = (
        tmp_path
        / "telegram_dispatch_progress.json"
    )

    listener = load_listener(
        monkeypatch,
        commercial_executor_fleet,
    )

    progress_store = (
        TelegramDispatchProgressStore(
            storage_path=storage_path
        )
    )

    first_client = (
        FirstAttemptHttpClient()
    )

    monkeypatch.setattr(
        listener,
        "remote_dispatch_progress_store",
        progress_store,
        raising=False,
    )

    monkeypatch.setattr(
        listener,
        "remote_http_client",
        first_client,
        raising=False,
    )

    monkeypatch.setattr(
        listener,
        "PositionSizingEngine",
        FakePositionSizingEngine,
    )

    listener.processed_message_keys.clear()

    incoming_signal = (
        make_incoming_signal()
    )

    try:
        listener.process_remote_vps_signal(
            incoming_signal
        )
    except httpx.ReadTimeout:
        pass

    assert first_client.read_agent_ids == [
        "trusted-agent-001",
        "trusted-agent-002",
    ]

    assert len(
        first_client.sent_missions
    ) == 2

    first_progress = progress_store.get(
        chat_id=-1001,
        message_id=168401,
        agent_id="trusted-agent-001",
    )

    second_progress = progress_store.get(
        chat_id=-1001,
        message_id=168401,
        agent_id="trusted-agent-002",
    )

    assert first_progress is not None
    assert second_progress is not None

    assert first_progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    assert second_progress.status == (
        TelegramDispatchStatus.PENDING
    )

    assert (
        first_progress.mission
        == first_client.sent_missions[0]
    )

    assert (
        second_progress.mission
        == first_client.sent_missions[1]
    )

    pending_mission_before_restart = (
        second_progress.mission
    )

    submitted_mission_before_restart = (
        first_progress.mission
    )

    # Simulate Telegram executor restart.
    restarted_listener = load_listener(
        monkeypatch,
        commercial_executor_fleet,
    )

    restored_store = (
        TelegramDispatchProgressStore(
            storage_path=storage_path
        )
    )

    retry_client = (
        RetryOnlyHttpClient()
    )

    monkeypatch.setattr(
        restarted_listener,
        "remote_dispatch_progress_store",
        restored_store,
        raising=False,
    )

    monkeypatch.setattr(
        restarted_listener,
        "remote_http_client",
        retry_client,
        raising=False,
    )

    monkeypatch.setattr(
        restarted_listener,
        "PositionSizingEngine",
        FailIfSizingEngineRuns,
    )

    restarted_listener.processed_message_keys.clear()

    retry_result = (
        restarted_listener
        .process_remote_vps_signal(
            make_incoming_signal()
        )
    )

    assert retry_result["status"] == (
        "submitted"
    )

    assert len(
        retry_client.sent_missions
    ) == 1

    retried_mission = (
        retry_client.sent_missions[0]
    )

    assert (
        retried_mission
        == pending_mission_before_restart
    )

    assert (
        retried_mission.created_at
        == pending_mission_before_restart.created_at
    )

    assert (
        retried_mission.expires_at
        == pending_mission_before_restart.expires_at
    )

    assert (
        retried_mission.volume
        == pending_mission_before_restart.volume
    )

    assert (
        retried_mission.mission_id
        == pending_mission_before_restart.mission_id
    )

    assert (
        retried_mission.agent_id
        == "trusted-agent-002"
    )

    final_first_progress = (
        restored_store.get(
            chat_id=-1001,
            message_id=168401,
            agent_id="trusted-agent-001",
        )
    )

    final_second_progress = (
        restored_store.get(
            chat_id=-1001,
            message_id=168401,
            agent_id="trusted-agent-002",
        )
    )

    assert final_first_progress is not None
    assert final_second_progress is not None

    assert final_first_progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    assert final_second_progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    assert (
        final_first_progress.mission
        == submitted_mission_before_restart
    )

    assert (
        final_second_progress.mission
        == pending_mission_before_restart
    )