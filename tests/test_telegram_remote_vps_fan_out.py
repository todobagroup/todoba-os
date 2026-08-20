"""
TODOBA Telegram Remote VPS Fan-Out Tests

Proof:

Telegram IncomingSignal
->
configured Execution Targets
->
per-target Broker State
->
per-target risk and sizing
->
one target-specific ExecutionMission per target

Legacy single-target behavior remains protected by the
existing Telegram REMOTE_VPS mission flow tests.
"""

import importlib
import json
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)


TRUSTED_AGENTS = [
    {
        "agent_id": "trusted-agent-001",
        "agent_secret": "agent-secret-a",
        "account_fingerprint": "account-a",
        "execution_mission_signing_secret": (
            "execution-signing-a"
        ),
        "control_mission_signing_secret": (
            "control-signing-a"
        ),
    },
    {
        "agent_id": "trusted-agent-002",
        "agent_secret": "agent-secret-b",
        "account_fingerprint": "account-b",
        "execution_mission_signing_secret": (
            "execution-signing-b"
        ),
        "control_mission_signing_secret": (
            "control-signing-b"
        ),
    },
]


EXECUTION_TARGETS = [
    {
        "agent_id": "trusted-agent-001",
        "account_fingerprint": "account-a",
    },
    {
        "agent_id": "trusted-agent-002",
        "account_fingerprint": "account-b",
    },
]


def configure_multi_target_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    legacy_agent_id: str,
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
            "telegram-executor-fan-out"
        ),
        "TODOBA_EXECUTOR_SECRET": (
            "fan-out-executor-secret"
        ),
        "TODOBA_TRUSTED_AGENT_ID": (
            legacy_agent_id
        ),
        "TODOBA_TRUSTED_AGENTS_JSON": (
            json.dumps(
                TRUSTED_AGENTS
            )
        ),
        "TODOBA_EXECUTION_TARGETS_JSON": (
            json.dumps(
                EXECUTION_TARGETS
            )
        ),
    }

    for name, value in environment.items():
        monkeypatch.setenv(
            name,
            value,
        )


def reload_multi_target_config(
    monkeypatch: pytest.MonkeyPatch,
    *,
    legacy_agent_id: str,
):
    configure_multi_target_environment(
        monkeypatch,
        legacy_agent_id=legacy_agent_id,
    )

    import backend.config as config

    return importlib.reload(
        config
    )


def load_multi_target_listener(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    legacy_agent_id: str = (
        "legacy-agent-must-not-route"
    ),
):
    reload_multi_target_config(
        monkeypatch,
        legacy_agent_id=legacy_agent_id,
    )

    import backend.integrations.telegram_dispatch_progress_store as progress_store_module

    real_progress_store = (
        progress_store_module.TelegramDispatchProgressStore
    )

    def build_test_progress_store(
        *,
        storage_path: Path,
    ):
        return real_progress_store(
            storage_path=(
                tmp_path
                / "telegram_dispatch_progress.json"
            )
        )

    monkeypatch.setattr(
        progress_store_module,
        "TelegramDispatchProgressStore",
        build_test_progress_store,
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
        sender="fan-out-proof",
        sender_id=1,
        chat_id=-1001,
        message_id=168101,
        received_at=datetime.now(
            UTC
        ),
    )


class FakeRemoteHttpClient:
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
            "legacy-agent-must-not-route": (
                make_broker_state(
                    agent_id=(
                        "legacy-agent-must-not-route"
                    ),
                    account_fingerprint=(
                        "legacy-account"
                    ),
                    equity=500.0,
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

        return {
            "status": "persisted",
            "mission_id": mission.mission_id,
        }


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


def test_remote_vps_multi_agent_config_does_not_require_legacy_agent_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = reload_multi_target_config(
        monkeypatch,
        legacy_agent_id="",
    )

    config.validate_telegram_config()


def test_remote_vps_listener_composes_configured_execution_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    listener = load_multi_target_listener(
        monkeypatch,
        tmp_path,
    )

    targets = (
        listener
        .remote_execution_target_registry
        .all()
    )

    assert [
        (
            target.agent_id,
            target.account_fingerprint,
        )
        for target in targets
    ] == [
        (
            "trusted-agent-001",
            "account-a",
        ),
        (
            "trusted-agent-002",
            "account-b",
        ),
    ]


def test_remote_vps_listener_fans_out_to_each_execution_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    listener = load_multi_target_listener(
        monkeypatch,
        tmp_path,
    )

    fake_http_client = (
        FakeRemoteHttpClient()
    )

    monkeypatch.setattr(
        listener,
        "remote_http_client",
        fake_http_client,
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

    first_result = (
        listener.process_remote_vps_signal(
            incoming_signal
        )
    )

    second_result = (
        listener.process_remote_vps_signal(
            incoming_signal
        )
    )

    assert first_result["status"] == (
        "submitted"
    )

    assert second_result["status"] == (
        "duplicate"
    )

    assert fake_http_client.read_agent_ids == [
        "trusted-agent-001",
        "trusted-agent-002",
    ]

    assert len(
        fake_http_client.sent_missions
    ) == 2

    first_mission = (
        fake_http_client.sent_missions[0]
    )

    second_mission = (
        fake_http_client.sent_missions[1]
    )

    assert first_mission.mission_id == (
        "telegram-1001-168101-"
        "trusted-agent-001"
    )

    assert second_mission.mission_id == (
        "telegram-1001-168101-"
        "trusted-agent-002"
    )

    assert first_mission.agent_id == (
        "trusted-agent-001"
    )

    assert second_mission.agent_id == (
        "trusted-agent-002"
    )

    assert (
        first_mission.account_fingerprint
        == "account-a"
    )

    assert (
        second_mission.account_fingerprint
        == "account-b"
    )

    assert first_mission.volume == 0.01
    assert second_mission.volume == 0.02

    assert first_mission.sequence == 168101
    assert second_mission.sequence == 168101

    target_results = (
        first_result["target_results"]
    )

    assert [
        result["agent_id"]
        for result in target_results
    ] == [
        "trusted-agent-001",
        "trusted-agent-002",
    ]

    assert [
        result["status"]
        for result in target_results
    ] == [
        "submitted",
        "submitted",
    ]

    assert [
        result["mission"].mission_id
        for result in target_results
    ] == [
        (
            "telegram-1001-168101-"
            "trusted-agent-001"
        ),
        (
            "telegram-1001-168101-"
            "trusted-agent-002"
        ),
    ]


def test_remote_vps_rejects_target_when_broker_state_agent_does_not_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    listener = load_multi_target_listener(
        monkeypatch,
        tmp_path,
    )

    fake_http_client = (
        FakeRemoteHttpClient()
    )

    fake_http_client.states[
        "trusted-agent-001"
    ] = make_broker_state(
        agent_id="trusted-agent-999",
        account_fingerprint="account-a",
        equity=1000.0,
    )

    monkeypatch.setattr(
        listener,
        "remote_http_client",
        fake_http_client,
        raising=False,
    )

    monkeypatch.setattr(
        listener,
        "PositionSizingEngine",
        FakePositionSizingEngine,
    )

    listener.processed_message_keys.clear()

    result = (
        listener.process_remote_vps_signal(
            make_incoming_signal()
        )
    )

    assert result["status"] == (
        "partially_submitted"
    )

    assert fake_http_client.read_agent_ids == [
        "trusted-agent-001",
        "trusted-agent-002",
    ]

    assert len(
        fake_http_client.sent_missions
    ) == 1

    mission = (
        fake_http_client.sent_missions[0]
    )

    assert mission.agent_id == (
        "trusted-agent-002"
    )

    assert mission.account_fingerprint == (
        "account-b"
    )

    target_results = (
        result["target_results"]
    )

    assert target_results[0]["status"] == (
        "broker_state_rejected"
    )

    assert target_results[0]["reason"] == (
        "Broker state Agent does not "
        "match execution target."
    )

    assert target_results[1]["status"] == (
        "submitted"
    )


def test_remote_vps_rejects_account_mismatch_without_blocking_other_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    listener = load_multi_target_listener(
        monkeypatch,
        tmp_path,
    )

    fake_http_client = (
        FakeRemoteHttpClient()
    )

    fake_http_client.states[
        "trusted-agent-001"
    ] = make_broker_state(
        agent_id="trusted-agent-001",
        account_fingerprint="wrong-account",
        equity=1000.0,
    )

    monkeypatch.setattr(
        listener,
        "remote_http_client",
        fake_http_client,
        raising=False,
    )

    monkeypatch.setattr(
        listener,
        "PositionSizingEngine",
        FakePositionSizingEngine,
    )

    listener.processed_message_keys.clear()

    result = (
        listener.process_remote_vps_signal(
            make_incoming_signal()
        )
    )

    assert result["status"] == (
        "partially_submitted"
    )

    assert fake_http_client.read_agent_ids == [
        "trusted-agent-001",
        "trusted-agent-002",
    ]

    assert len(
        fake_http_client.sent_missions
    ) == 1

    mission = (
        fake_http_client.sent_missions[0]
    )

    assert mission.mission_id == (
        "telegram-1001-168101-"
        "trusted-agent-002"
    )

    assert mission.agent_id == (
        "trusted-agent-002"
    )

    assert mission.account_fingerprint == (
        "account-b"
    )

    target_results = (
        result["target_results"]
    )

    assert target_results[0]["status"] == (
        "broker_state_rejected"
    )

    assert target_results[0]["reason"] == (
        "Broker state account_fingerprint "
        "does not match execution target."
    )

    assert target_results[1]["status"] == (
        "submitted"
    )