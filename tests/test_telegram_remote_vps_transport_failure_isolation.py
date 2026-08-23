"""
TODOBA Telegram Multi-Target Transport Failure Isolation Tests

CAP 3F proof:

One remote execution target transport failure must never
prevent later configured targets from being processed.

Required rules:

- Broker State read failure for one target:
  record a target-local transport failure
  do not create a mission from unavailable Broker State
  continue to later targets

- new mission send failure:
  keep the exact prepared mission durably PENDING
  record a target-local transport failure
  continue to later targets

- persisted PENDING resend failure:
  keep the exact persisted mission PENDING
  never rebuild the mission
  continue to later targets

Transport isolation must not:
- alter target ownership
- reuse another target's Broker State
- rebuild a persisted mission
- mark failed delivery SUBMITTED
- block a healthy later target
"""

import importlib
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.integrations.telegram_dispatch_recovery import (
    TelegramDispatchRecovery,
)
from backend.integrations.telegram_dispatch_progress_store import (
    TelegramDispatchStatus,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)








CHAT_ID = -1001
MESSAGE_ID = 168801


def configure_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = {
        "TELEGRAM_API_ID": "1",
        "TELEGRAM_API_HASH": "test-hash",
        "TELEGRAM_SESSION": "test-session",
        "TELEGRAM_SIGNAL_GROUP_ID": str(
            CHAT_ID
        ),
        "TELEGRAM_EXECUTION_MODE": "REMOTE_VPS",
        "TELEGRAM_AUTHORIZED_SENDER_IDS": "1",
        "MT5_MAX_SPREAD_POINTS": "100",
        "TODOBA_CLOUD_BASE_URL": (
            "https://api.todobagroup.com"
        ),
        "TODOBA_EXECUTOR_ID": (
            "telegram-executor-transport-isolation"
        ),
        "TODOBA_EXECUTOR_SECRET": (
            "transport-isolation-secret"
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
            (
                "trusted-agent-002",
                "account-b",
            ),
        )
    )

    # Keep telegram_listener's real relative
    # data/trading dispatch store inside pytest temp.
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

    listener = importlib.import_module(
        "backend.integrations.telegram_listener"
    )

    listener.processed_message_keys.clear()

    return listener


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


def make_signal() -> IncomingSignal:
    return IncomingSignal(
        source="telegram",
        message=(
            "Sell GOLD NOW\n"
            "SL: 4380\n"
            "TP: 4340"
        ),
        sender="transport-isolation-proof",
        sender_id=1,
        chat_id=CHAT_ID,
        message_id=MESSAGE_ID,
        received_at=datetime.now(
            UTC
        ),
    )


def make_persisted_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=(
            "telegram-1001-168801-"
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
        created_at="2026-08-21T00:00:00Z",
        expires_at="2099-01-01T00:00:00Z",
        sequence=MESSAGE_ID,
        security_sequence=0,
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


class FaultInjectingRemoteHttpClient:
    def __init__(
        self,
        *,
        read_failure_agent_ids: set[str] | None = None,
        send_failure_agent_ids: set[str] | None = None,
    ) -> None:
        self.read_failure_agent_ids = (
            set()
            if read_failure_agent_ids is None
            else set(
                read_failure_agent_ids
            )
        )

        self.send_failure_agent_ids = (
            set()
            if send_failure_agent_ids is None
            else set(
                send_failure_agent_ids
            )
        )

        self.read_agent_ids: list[str] = []
        self.sent_missions: list[
            ExecutionMission
        ] = []

        self.states = {
            "trusted-agent-001": (
                make_broker_state(
                    agent_id="trusted-agent-001",
                    account_fingerprint="account-a",
                    equity=1000.0,
                )
            ),
            "trusted-agent-002": (
                make_broker_state(
                    agent_id="trusted-agent-002",
                    account_fingerprint="account-b",
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

        if (
            agent_id
            in self.read_failure_agent_ids
        ):
            raise TimeoutError(
                "proof Broker State timeout"
            )

        return self.states[
            agent_id
        ]

    def send(
        self,
        mission: ExecutionMission,
    ) -> dict:
        self.sent_missions.append(
            mission
        )

        if (
            mission.agent_id
            in self.send_failure_agent_ids
        ):
            raise TimeoutError(
                "proof mission send timeout"
            )

        return {
            "status": "persisted",
            "mission_id": mission.mission_id,
        }


def install_runtime_fakes(
    *,
    monkeypatch: pytest.MonkeyPatch,
    listener,
    http_client: FaultInjectingRemoteHttpClient,
) -> None:
    monkeypatch.setattr(
        listener,
        "remote_http_client",
        http_client,
        raising=False,
    )

    monkeypatch.setattr(
        listener,
        "PositionSizingEngine",
        FakePositionSizingEngine,
    )


def test_broker_state_transport_failure_does_not_block_later_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
        commercial_executor_fleet,
    )

    http_client = FaultInjectingRemoteHttpClient(
        read_failure_agent_ids={
            "trusted-agent-001",
        }
    )

    install_runtime_fakes(
        monkeypatch=monkeypatch,
        listener=listener,
        http_client=http_client,
    )

    result = listener.process_remote_vps_signal(
        make_signal()
    )

    assert result["status"] == (
        "partially_submitted"
    )

    assert http_client.read_agent_ids == [
        "trusted-agent-001",
        "trusted-agent-002",
    ]

    assert len(
        http_client.sent_missions
    ) == 1

    healthy_mission = (
        http_client.sent_missions[0]
    )

    assert healthy_mission.agent_id == (
        "trusted-agent-002"
    )

    assert (
        healthy_mission.account_fingerprint
        == "account-b"
    )

    failed_progress = (
        listener.remote_dispatch_progress_store.get(
            chat_id=CHAT_ID,
            message_id=MESSAGE_ID,
            agent_id="trusted-agent-001",
        )
    )

    assert failed_progress is None

    healthy_progress = (
        listener.remote_dispatch_progress_store.get(
            chat_id=CHAT_ID,
            message_id=MESSAGE_ID,
            agent_id="trusted-agent-002",
        )
    )

    assert healthy_progress is not None
    assert healthy_progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    target_results = result[
        "target_results"
    ]

    assert target_results[0][
        "agent_id"
    ] == "trusted-agent-001"

    assert target_results[0][
        "status"
    ] == "transport_failed"

    assert target_results[0][
        "operation"
    ] == "read_broker_state"

    assert target_results[1][
        "agent_id"
    ] == "trusted-agent-002"

    assert target_results[1][
        "status"
    ] == "submitted"


def test_new_mission_send_failure_stays_pending_and_does_not_block_later_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
        commercial_executor_fleet,
    )

    http_client = FaultInjectingRemoteHttpClient(
        send_failure_agent_ids={
            "trusted-agent-001",
        }
    )

    install_runtime_fakes(
        monkeypatch=monkeypatch,
        listener=listener,
        http_client=http_client,
    )

    result = listener.process_remote_vps_signal(
        make_signal()
    )

    assert result["status"] == (
        "partially_submitted"
    )

    assert http_client.read_agent_ids == [
        "trusted-agent-001",
        "trusted-agent-002",
    ]

    assert [
        mission.agent_id
        for mission in http_client.sent_missions
    ] == [
        "trusted-agent-001",
        "trusted-agent-002",
    ]

    failed_progress = (
        listener.remote_dispatch_progress_store.get(
            chat_id=CHAT_ID,
            message_id=MESSAGE_ID,
            agent_id="trusted-agent-001",
        )
    )

    healthy_progress = (
        listener.remote_dispatch_progress_store.get(
            chat_id=CHAT_ID,
            message_id=MESSAGE_ID,
            agent_id="trusted-agent-002",
        )
    )

    assert failed_progress is not None
    assert healthy_progress is not None

    assert failed_progress.status == (
        TelegramDispatchStatus.PENDING
    )

    assert healthy_progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    failed_sent_mission = (
        http_client.sent_missions[0]
    )

    assert (
        failed_progress.mission
        == failed_sent_mission
    )

    target_results = result[
        "target_results"
    ]

    assert target_results[0][
        "status"
    ] == "transport_failed"

    assert target_results[0][
        "operation"
    ] == "send_mission"

    assert target_results[0][
        "mission"
    ] == failed_progress.mission

    assert target_results[1][
        "status"
    ] == "submitted"


def test_persisted_pending_resend_failure_preserves_exact_mission_and_does_not_block_later_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
        commercial_executor_fleet,
    )

    persisted_mission = (
        make_persisted_mission()
    )

    prepared = (
        listener.remote_dispatch_progress_store.prepare(
            chat_id=CHAT_ID,
            message_id=MESSAGE_ID,
            mission=persisted_mission,
        )
    )

    assert prepared.status == (
        TelegramDispatchStatus.PENDING
    )

    http_client = FaultInjectingRemoteHttpClient(
        send_failure_agent_ids={
            "trusted-agent-001",
        }
    )

    install_runtime_fakes(
        monkeypatch=monkeypatch,
        listener=listener,
        http_client=http_client,
    )

    result = listener.process_remote_vps_signal(
        make_signal()
    )

    assert result["status"] == (
        "partially_submitted"
    )

    assert http_client.read_agent_ids == [
        "trusted-agent-002",
    ]

    assert len(
        http_client.sent_missions
    ) == 2

    resent_mission = (
        http_client.sent_missions[0]
    )

    healthy_mission = (
        http_client.sent_missions[1]
    )

    assert resent_mission == (
        persisted_mission
    )

    assert healthy_mission.agent_id == (
        "trusted-agent-002"
    )

    failed_progress = (
        listener.remote_dispatch_progress_store.get(
            chat_id=CHAT_ID,
            message_id=MESSAGE_ID,
            agent_id="trusted-agent-001",
        )
    )

    healthy_progress = (
        listener.remote_dispatch_progress_store.get(
            chat_id=CHAT_ID,
            message_id=MESSAGE_ID,
            agent_id="trusted-agent-002",
        )
    )

    assert failed_progress is not None
    assert healthy_progress is not None

    assert failed_progress.status == (
        TelegramDispatchStatus.PENDING
    )

    assert failed_progress.mission == (
        persisted_mission
    )

    assert healthy_progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    target_results = result[
        "target_results"
    ]

    assert target_results[0][
        "status"
    ] == "transport_failed"

    assert target_results[0][
        "operation"
    ] == "send_mission"

    assert target_results[0][
        "mission"
    ] == persisted_mission

    assert target_results[1][
        "status"
    ] == "submitted"