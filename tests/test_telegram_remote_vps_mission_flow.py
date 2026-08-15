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
from datetime import timedelta
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
                "XMGlobal-MT5 9:336627882"
            ),
            "equity": 2622.34,
            "open_position_count": 0,
            "pending_order_count": 0,
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


@pytest.mark.parametrize(
    (
        "message",
        "expected_order_type",
        "expected_entry",
        "expected_sl",
        "expected_tp",
    ),
    [
        (
            "BUY GOLD LIMIT\n"
            "ENTRY: 4350\n"
            "SL: 4330\n"
            "TP: 4390",
            "BUY LIMIT",
            4350.0,
            4330.0,
            4390.0,
        ),
        (
            "SELL GOLD LIMIT\n"
            "ENTRY: 4380\n"
            "SL: 4400\n"
            "TP: 4340",
            "SELL LIMIT",
            4380.0,
            4400.0,
            4340.0,
        ),
        (
            "BUY GOLD STOP\n"
            "ENTRY: 4380\n"
            "SL: 4360\n"
            "TP: 4420",
            "BUY STOP",
            4380.0,
            4360.0,
            4420.0,
        ),
        (
            "SELL GOLD STOP\n"
            "ENTRY: 4350\n"
            "SL: 4370\n"
            "TP: 4310",
            "SELL STOP",
            4350.0,
            4370.0,
            4310.0,
        ),
    ],
)
def test_remote_vps_listener_preserves_pending_order(
    monkeypatch: pytest.MonkeyPatch,
    message,
    expected_order_type,
    expected_entry,
    expected_sl,
    expected_tp,
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
        message=message,
        sender="proof174",
        sender_id=1,
        chat_id=-1001,
        message_id=174001,
        received_at=datetime.now(
            UTC
        ),
    )

    result = listener.process_remote_vps_signal(
        incoming_signal
    )

    assert result["status"] == "submitted"
    assert len(fake_http_client.sent_missions) == 1

    mission = fake_http_client.sent_missions[0]

    assert mission.symbol == "XAUUSD"
    assert mission.order_type == expected_order_type
    assert mission.entry == expected_entry
    assert mission.sl == expected_sl
    assert mission.tp == expected_tp
    assert mission.volume == 0.03
    assert mission.magic_number == 10001
    assert mission.comment == "TODOBA"


def test_remote_vps_rejects_at_active_trade_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listener = load_remote_listener(
        monkeypatch
    )

    class FullRemoteHttpClient(
        FakeRemoteHttpClient
    ):
        def read_latest_broker_state(
            self,
            *,
            agent_id: str,
        ) -> dict:
            state = super().read_latest_broker_state(
                agent_id=agent_id
            )

            return {
                **state,
                "open_position_count": 6,
                "pending_order_count": 4,
            }

    fake_http_client = FullRemoteHttpClient()

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
            "BUY GOLD NOW\n"
            "SL: 4330\n"
            "TP: 4370"
        ),
        sender="proof175",
        sender_id=1,
        chat_id=-1001,
        message_id=175001,
        received_at=datetime.now(
            UTC
        ),
    )

    result = listener.process_remote_vps_signal(
        incoming_signal
    )

    assert result["status"] == "decision_rejected"
    assert len(fake_http_client.sent_missions) == 0

    assert result["production"].decision.reason == (
        "Maximum active trade limit reached: "
        "10/10 (positions=6, pending=4)."
    )


@pytest.mark.parametrize(
    (
        "received_at",
        "expected_reason",
    ),
    [
        (
            (
                datetime.now(
                    UTC
                )
                - timedelta(
                    seconds=31
                )
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            ),
            "Broker state is stale.",
        ),
        (
            None,
            (
                "Broker state received_at "
                "is required."
            ),
        ),
        (
            "not-a-timestamp",
            (
                "Broker state received_at "
                "is invalid."
            ),
        ),
    ],
)
def test_remote_vps_rejects_untrusted_broker_state(
    monkeypatch: pytest.MonkeyPatch,
    received_at,
    expected_reason,
) -> None:
    listener = load_remote_listener(
        monkeypatch
    )

    class UntrustedRemoteHttpClient(
        FakeRemoteHttpClient
    ):
        def read_latest_broker_state(
            self,
            *,
            agent_id: str,
        ) -> dict:
            state = super().read_latest_broker_state(
                agent_id=agent_id
            )

            if received_at is None:
                state.pop(
                    "received_at"
                )
            else:
                state["received_at"] = (
                    received_at
                )

            return state

    fake_http_client = (
        UntrustedRemoteHttpClient()
    )

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
            "SELL GOLD NOW\n"
            "SL: 4400\n"
            "TP: 4370"
        ),
        sender="proof177",
        sender_id=1,
        chat_id=-1001,
        message_id=177001,
        received_at=datetime.now(
            UTC
        ),
    )

    result = (
        listener.process_remote_vps_signal(
            incoming_signal
        )
    )

    assert (
        result["status"]
        == "broker_state_rejected"
    )
    assert result["reason"] == expected_reason
    assert len(
        fake_http_client.sent_missions
    ) == 0