"""
TODOBA Telegram Remote VPS Quick Control Tests

Proof:

authorized bilingual Telegram control command
->
commercial execution target fleet
->
fresh authoritative broker state
->
one ControlMission per eligible target
->
authenticated Cloud Control transport

Control transport failures are isolated per target.
The same Telegram control message is not executed twice.
"""

import importlib
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
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

    monkeypatch.chdir(
        tmp_path
    )

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
            "telegram-executor-001"
        ),
        "TODOBA_EXECUTOR_SECRET": (
            "quick-control-test-secret"
        ),
    }

    for name, value in environment.items():
        monkeypatch.setenv(
            name,
            value,
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


def make_state(
    *,
    agent_id: str,
    account_fingerprint: str,
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
        "equity": 1000.0,
        "open_position_count": 4,
        "pending_order_count": 0,
        "symbol": "XAUUSD",
        "bid": 4600.0,
        "ask": 4600.5,
        "spread_points": 50.0,
    }


class FakeRemoteControlHttpClient:
    def __init__(self) -> None:
        self.read_agent_ids: list[str] = []
        self.sent_missions = []

        self.states = {
            "trusted-agent-001": make_state(
                agent_id="trusted-agent-001",
                account_fingerprint="account-a",
            ),
            "trusted-agent-002": make_state(
                agent_id="trusted-agent-002",
                account_fingerprint="account-b",
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


def make_signal(
    message: str,
    *,
    sender_id: int = 1,
    message_id: int = 188001,
) -> IncomingSignal:
    return IncomingSignal(
        source="telegram",
        message=message,
        sender="operator",
        sender_id=sender_id,
        chat_id=-1001,
        message_id=message_id,
        received_at=datetime.now(
            UTC
        ),
    )


def test_quick_control_fans_out_to_each_execution_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
        commercial_executor_fleet,
    )

    fake_client = (
        FakeRemoteControlHttpClient()
    )

    monkeypatch.setattr(
        listener,
        "remote_control_http_client",
        fake_client,
        raising=False,
    )

    listener.processed_message_keys.clear()

    incoming = make_signal(
        "TODOBA CLOSE BUY"
    )

    action = (
        listener.parse_control_command(
            incoming.message
        )
    )

    assert action is ControlAction.CLOSE_BUY

    first_result = (
        listener.process_remote_vps_control(
            incoming,
            action,
        )
    )

    second_result = (
        listener.process_remote_vps_control(
            incoming,
            action,
        )
    )

    assert first_result["status"] == (
        "submitted"
    )

    assert second_result["status"] == (
        "duplicate"
    )

    assert fake_client.read_agent_ids == [
        "trusted-agent-001",
        "trusted-agent-002",
    ]

    assert len(
        fake_client.sent_missions
    ) == 2

    first = fake_client.sent_missions[0]
    second = fake_client.sent_missions[1]

    assert first.mission_id == (
        "telegram-control-1001-188001-"
        "trusted-agent-001"
    )

    assert second.mission_id == (
        "telegram-control-1001-188001-"
        "trusted-agent-002"
    )

    assert first.agent_id == (
        "trusted-agent-001"
    )

    assert second.agent_id == (
        "trusted-agent-002"
    )

    assert first.account_fingerprint == (
        "account-a"
    )

    assert second.account_fingerprint == (
        "account-b"
    )

    assert first.action is (
        ControlAction.CLOSE_BUY
    )

    assert second.action is (
        ControlAction.CLOSE_BUY
    )

    assert first.symbol == "XAUUSD"
    assert second.symbol == "XAUUSD"

    assert first.magic_number == 10001
    assert second.magic_number == 10001

    assert first.requested_by_sender_id == 1
    assert second.requested_by_sender_id == 1

    assert first.sequence == 188001
    assert second.sequence == 188001


@pytest.mark.parametrize(
    "message",
    [
        "TODOBA ĐÓNG SELL",
        "TODOBA CLOSE SELL",
    ],
)
def test_quick_control_preserves_bilingual_operator_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
    message,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
        commercial_executor_fleet,
    )

    fake_client = (
        FakeRemoteControlHttpClient()
    )

    monkeypatch.setattr(
        listener,
        "remote_control_http_client",
        fake_client,
        raising=False,
    )

    listener.processed_message_keys.clear()

    incoming = make_signal(
        message,
        message_id=188101,
    )

    action = (
        listener.parse_control_command(
            incoming.message
        )
    )

    assert action is ControlAction.CLOSE_SELL

    result = (
        listener.process_remote_vps_control(
            incoming,
            action,
        )
    )

    assert result["status"] == "submitted"

    assert [
        mission.action
        for mission in fake_client.sent_missions
    ] == [
        ControlAction.CLOSE_SELL,
        ControlAction.CLOSE_SELL,
    ]


def test_quick_control_isolates_offline_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
        commercial_executor_fleet,
    )

    class PartialClient(
        FakeRemoteControlHttpClient
    ):
        def read_latest_broker_state(
            self,
            *,
            agent_id: str,
        ) -> dict:
            self.read_agent_ids.append(
                agent_id
            )

            if agent_id == "trusted-agent-001":
                raise RuntimeError(
                    "broker state unavailable"
                )

            return self.states[
                agent_id
            ]

    fake_client = PartialClient()

    monkeypatch.setattr(
        listener,
        "remote_control_http_client",
        fake_client,
        raising=False,
    )

    listener.processed_message_keys.clear()

    incoming = make_signal(
        "TODOBA CLOSE GREEN",
        message_id=188201,
    )

    action = (
        listener.parse_control_command(
            incoming.message
        )
    )

    result = (
        listener.process_remote_vps_control(
            incoming,
            action,
        )
    )

    assert result["status"] == (
        "partially_submitted"
    )

    assert len(
        fake_client.sent_missions
    ) == 1

    assert (
        fake_client.sent_missions[0].agent_id
        == "trusted-agent-002"
    )

    assert (
        result["target_results"][0]["status"]
        == "transport_failed"
    )

    assert (
        result["target_results"][1]["status"]
        == "submitted"
    )


def test_quick_control_rejects_account_mismatch_without_blocking_other_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
        commercial_executor_fleet,
    )

    fake_client = (
        FakeRemoteControlHttpClient()
    )

    fake_client.states[
        "trusted-agent-001"
    ] = make_state(
        agent_id="trusted-agent-001",
        account_fingerprint="wrong-account",
    )

    monkeypatch.setattr(
        listener,
        "remote_control_http_client",
        fake_client,
        raising=False,
    )

    listener.processed_message_keys.clear()

    incoming = make_signal(
        "TODOBA CLOSE RED",
        message_id=188301,
    )

    action = (
        listener.parse_control_command(
            incoming.message
        )
    )

    result = (
        listener.process_remote_vps_control(
            incoming,
            action,
        )
    )

    assert result["status"] == (
        "partially_submitted"
    )

    assert len(
        fake_client.sent_missions
    ) == 1

    assert (
        fake_client.sent_missions[0].agent_id
        == "trusted-agent-002"
    )

    assert (
        result["target_results"][0]["status"]
        == "broker_state_rejected"
    )

    assert result[
        "target_results"
    ][0]["reason"] == (
        "Broker state account_fingerprint "
        "does not match execution target."
    )

    assert (
        result["target_results"][1]["status"]
        == "submitted"
    )


def test_quick_control_rejects_unauthorized_sender_before_remote_reads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    commercial_executor_fleet,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
        commercial_executor_fleet,
    )

    fake_client = (
        FakeRemoteControlHttpClient()
    )

    monkeypatch.setattr(
        listener,
        "remote_control_http_client",
        fake_client,
        raising=False,
    )

    listener.processed_message_keys.clear()

    incoming = make_signal(
        "TODOBA CLOSE BUY",
        sender_id=999,
        message_id=188401,
    )

    result = (
        listener.process_remote_vps_control(
            incoming,
            ControlAction.CLOSE_BUY,
        )
    )

    assert result == {
        "status": "unauthorized_sender",
        "sender_id": 999,
    }

    assert fake_client.read_agent_ids == []
    assert fake_client.sent_missions == []
