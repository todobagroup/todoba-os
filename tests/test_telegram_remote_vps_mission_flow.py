"""
TODOBA Telegram Remote VPS Production Flow Tests

Proof:

Telegram IncomingSignal
->
latest remote Broker State
->
TelegramTaskProducer
->
ExecutionMission
->
authenticated Cloud HTTP client

The same Telegram message must create only one mission.
"""

import importlib
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)


def load_remote_listener(
    monkeypatch: pytest.MonkeyPatch,
):
    environment = {
        "TELEGRAM_API_ID": "1",
        "TELEGRAM_API_HASH": "test-hash",
        "TELEGRAM_SESSION": "test-session",
        "TELEGRAM_SIGNAL_GROUP_ID": "-1001",
        "TELEGRAM_EXECUTION_MODE": "REMOTE_VPS",
        "MT5_MAX_SPREAD_POINTS": "100",
        "TODOBA_CLOUD_BASE_URL": (
            "https://api.todobagroup.com"
        ),
        "TODOBA_TRUSTED_AGENT_ID": (
            "trusted-agent-001"
        ),
        "TODOBA_EXECUTOR_ID": (
            "telegram-executor-001"
        ),
        "TODOBA_EXECUTOR_SECRET": (
            "proof169-executor-secret"
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


class FakeRemoteHttpClient:
    def __init__(self) -> None:
        self.read_agent_ids: list[str] = []
        self.sent_missions = []

    def read_latest_broker_state(
        self,
        *,
        agent_id: str,
    ) -> dict:
        self.read_agent_ids.append(
            agent_id
        )

        return {
            "status": "available",
            "agent_id": agent_id,
            "account_fingerprint": (
                "XMGlobal-MT5 9:336627882"
            ),
            "equity": 2622.34,
            "open_position_count": 0,
            "symbol": "XAUUSD",
            "bid": 4365.83,
            "ask": 4366.08,
            "spread_points": 25.0,
        }

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


def test_remote_vps_listener_submits_each_telegram_message_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listener = load_remote_listener(
        monkeypatch
    )

    fake_http_client = FakeRemoteHttpClient()

    monkeypatch.setattr(
        listener,
        "remote_http_client",
        fake_http_client,
        raising=False,
    )

    listener.processed_message_keys.clear()

    incoming_signal = IncomingSignal(
        source="telegram",
        message=(
            "Sell GOLD NOW\n"
            "SL: 4380\n"
            "TP: 4340"
        ),
        sender="proof169",
        sender_id=1,
        chat_id=-1001,
        message_id=168001,
        received_at=datetime.now(
            UTC
        ),
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

    assert first_result["status"] == "submitted"
    assert second_result["status"] == "duplicate"

    assert fake_http_client.read_agent_ids == [
        "trusted-agent-001"
    ]

    assert len(
        fake_http_client.sent_missions
    ) == 1

    mission = fake_http_client.sent_missions[0]

    assert mission.mission_id == (
        "telegram-1001-168001"
    )
    assert mission.agent_id == (
        "trusted-agent-001"
    )
    assert mission.account_fingerprint == (
        "XMGlobal-MT5 9:336627882"
    )
    assert mission.symbol == "XAUUSD"
    assert mission.order_type == "SELL NOW"
    assert mission.volume == 0.03
    assert mission.entry is None
    assert mission.sl == 4380.0
    assert mission.tp == 4340.0
    assert mission.magic_number == 10001
    assert mission.comment == "TODOBA"
    assert mission.sequence == 168001

    assert first_result["cloud_response"] == {
        "status": "persisted",
        "mission_id": "telegram-1001-168001",
    }