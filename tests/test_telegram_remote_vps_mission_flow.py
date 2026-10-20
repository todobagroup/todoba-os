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
    commercial_executor_fleet,
    tmp_path: Path,
):
    commercial_executor_fleet(
        (
            (
                "trusted-agent-001",
                "XMGlobal-MT5 9:336627882",
            ),
        )
    )

    # telegram_listener currently stores dispatch progress
    # beneath relative Path("data"). Move the test working
    # directory so that durable dispatch state is isolated.
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
    commercial_executor_fleet,
    tmp_path: Path,
) -> None:
    listener = load_remote_listener(
        monkeypatch,
        commercial_executor_fleet,
        tmp_path,
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
        "telegram-1001-168001-trusted-agent-001"
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

    assert len(
        first_result["target_results"]
    ) == 1

    first_target_result = (
        first_result["target_results"][0]
    )

    assert first_target_result["agent_id"] == (
        "trusted-agent-001"
    )

    assert (
        first_target_result["status"]
        == "submitted"
    )

    assert (
        first_target_result["mission"]
        == mission
    )

    assert first_target_result["cloud_response"] == {
        "status": "persisted",
        "mission_id": (
            "telegram-1001-168001-"
            "trusted-agent-001"
        ),
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
    commercial_executor_fleet,
    tmp_path: Path,
    message,
    expected_order_type,
    expected_entry,
    expected_sl,
    expected_tp,
) -> None:
    listener = load_remote_listener(
        monkeypatch,
        commercial_executor_fleet,
        tmp_path,
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
    commercial_executor_fleet,
    tmp_path: Path,
) -> None:
    listener = load_remote_listener(
        monkeypatch,
        commercial_executor_fleet,
        tmp_path,
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

    assert result["status"] == "rejected"

    assert len(
        result["target_results"]
    ) == 1

    target_result = (
        result["target_results"][0]
    )

    assert target_result["agent_id"] == (
        "trusted-agent-001"
    )

    assert (
        target_result["status"]
        == "decision_rejected"
    )

    assert len(
        fake_http_client.sent_missions
    ) == 0

    assert (
        target_result["production"]
        .decision.reason
        == (
            "Maximum active trade limit reached: "
            "10/10 (positions=6, pending=4)."
        )
    )


def test_remote_vps_rejects_unauthorized_sender(
    monkeypatch: pytest.MonkeyPatch,
    commercial_executor_fleet,
    tmp_path: Path,
) -> None:
    listener = load_remote_listener(
        monkeypatch,
        commercial_executor_fleet,
        tmp_path,
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
            "SELL GOLD NOW\n"
            "SL: 4400\n"
            "TP: 4370"
        ),
        sender="unauthorized",
        sender_id=999,
        chat_id=-1001,
        message_id=178001,
        received_at=datetime.now(
            UTC
        ),
    )

    result = (
        listener.process_remote_vps_signal(
            incoming_signal
        )
    )

    assert result == {
        "status": "unauthorized_sender",
        "sender_id": 999,
    }

    assert fake_http_client.read_agent_ids == []
    assert fake_http_client.sent_missions == []


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
    commercial_executor_fleet,
    tmp_path: Path,
    received_at,
    expected_reason,
) -> None:
    listener = load_remote_listener(
        monkeypatch,
        commercial_executor_fleet,
        tmp_path,
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

    assert result["status"] == "rejected"

    assert len(
        result["target_results"]
    ) == 1

    target_result = (
        result["target_results"][0]
    )

    assert target_result["agent_id"] == (
        "trusted-agent-001"
    )

    assert (
        target_result["status"]
        == "broker_state_rejected"
    )

    assert (
        target_result["reason"]
        == expected_reason
    )

    assert len(
        fake_http_client.sent_missions
    ) == 0


def test_remote_vps_rejects_same_trade_intent_with_new_message_id(
    monkeypatch: pytest.MonkeyPatch,
    commercial_executor_fleet,
    tmp_path: Path,
) -> None:
    """Same recent trade intent must not dispatch twice for one target."""

    listener = load_remote_listener(
        monkeypatch,
        commercial_executor_fleet,
        tmp_path,
    )

    fake_http_client = FakeRemoteHttpClient()
    monkeypatch.setattr(
        listener,
        "remote_http_client",
        fake_http_client,
        raising=False,
    )
    listener.processed_message_keys.clear()

    first_time = datetime.now(UTC)

    def make_signal(message_id: int, received_at: datetime):
        return IncomingSignal(
            source="telegram",
            message=(
                "BUY GOLD NOW\n"
                "SL: 4320\n"
                "TP: 4410"
            ),
            sender="synthetic-dedup-proof",
            sender_id=1,
            chat_id=-1001,
            message_id=message_id,
            received_at=received_at,
        )

    first = listener.process_remote_vps_signal(
        make_signal(168901, first_time)
    )

    second = listener.process_remote_vps_signal(
        make_signal(
            168902,
            first_time + timedelta(seconds=10),
        )
    )

    assert first["status"] == "submitted"
    assert len(fake_http_client.sent_missions) == 1, (
        "DUPLICATE_TRADE_INTENT_CREATED_SECOND_MISSION"
    )
    assert second["status"] != "submitted"


def test_timeout_restart_new_telegram_id_preserves_pending_mission(
    monkeypatch: pytest.MonkeyPatch,
    commercial_executor_fleet,
    tmp_path: Path,
) -> None:
    """HTTP timeout plus restart must not issue a new mission ID."""

    from backend.integrations.telegram_dispatch_progress_store import (
        TelegramDispatchProgressStore,
        TelegramDispatchStatus,
    )

    listener = load_remote_listener(
        monkeypatch,
        commercial_executor_fleet,
        tmp_path,
    )

    fake_http_client = FakeRemoteHttpClient()
    send_attempts = []

    def timeout_send(mission):
        send_attempts.append(mission.mission_id)
        raise TimeoutError("synthetic HTTP response timeout")

    monkeypatch.setattr(
        fake_http_client,
        "send",
        timeout_send,
    )
    monkeypatch.setattr(
        listener,
        "remote_http_client",
        fake_http_client,
        raising=False,
    )

    listener.processed_message_keys.clear()

    received_at = datetime.now(UTC)

    def incoming(message_id: int) -> IncomingSignal:
        return IncomingSignal(
            source="telegram",
            message=(
                "BUY GOLD NOW\n"
                "SL: 4320\n"
                "TP: 4410"
            ),
            sender="synthetic-timeout-proof",
            sender_id=1,
            chat_id=-1001,
            message_id=message_id,
            received_at=received_at,
        )

    first = listener.process_remote_vps_signal(
        incoming(169101)
    )

    assert first["status"] != "submitted"
    assert first["target_results"][0]["status"] == (
        "transport_failed"
    )
    assert len(send_attempts) == 1

    original_store = listener.remote_dispatch_progress_store
    original = original_store.get(
        chat_id=-1001,
        message_id=169101,
        agent_id="trusted-agent-001",
    )

    assert original is not None
    assert original.status == TelegramDispatchStatus.PENDING

    original_mission_id = original.mission.mission_id

    # Simulate a restart of durable dispatch state.
    restored_store = TelegramDispatchProgressStore(
        storage_path=original_store.storage_path,
    )

    monkeypatch.setattr(
        listener,
        "remote_dispatch_progress_store",
        restored_store,
    )
    listener.processed_message_keys.clear()

    second = listener.process_remote_vps_signal(
        incoming(169102)
    )

    assert second["status"] == "duplicate"
    assert len(send_attempts) == 1, (
        "DUPLICATE_TRIGGERED_NEW_HTTP_DISPATCH"
    )
    assert restored_store.size() == 1, (
        "DUPLICATE_CREATED_SECOND_PENDING_MISSION"
    )

    persisted = restored_store.get(
        chat_id=-1001,
        message_id=169101,
        agent_id="trusted-agent-001",
    )

    assert persisted is not None
    assert persisted.status == TelegramDispatchStatus.PENDING
    assert persisted.mission.mission_id == original_mission_id

def test_listener_blocks_http_when_persistence_commit_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
    commercial_executor_fleet,
    tmp_path: Path,
) -> None:
    """A failed durable prepare must never authorize HTTP dispatch."""
    import os
    from unittest.mock import patch

    from backend.integrations.telegram_dispatch_progress_store import (
        TelegramDispatchProgressStore,
    )

    listener = load_remote_listener(
        monkeypatch,
        commercial_executor_fleet,
        tmp_path,
    )

    fake_http_client = FakeRemoteHttpClient()
    monkeypatch.setattr(
        listener,
        "remote_http_client",
        fake_http_client,
        raising=False,
    )

    listener.processed_message_keys.clear()

    store = listener.remote_dispatch_progress_store
    storage = store.storage_path
    temporary = storage.with_name(storage.name + ".tmp")

    replacement = tmp_path / "r196_synthetic_replacement.json"
    replacement.write_text("[]", encoding="utf-8")

    original_replace = Path.replace
    injected = False

    def replace_with_race(self, target):
        nonlocal injected

        if self == temporary and Path(target) == storage:
            assert self.exists(), "DISPATCH_TEMP_NOT_CREATED"
            assert replacement.exists(), "REPLACEMENT_MISSING"
            os.replace(replacement, temporary)
            injected = True

        return original_replace(self, target)

    incoming = IncomingSignal(
        source="telegram",
        message=(
            "BUY GOLD NOW\n"
            "SL: 4320\n"
            "TP: 4410"
        ),
        sender="synthetic-persistence-failure",
        sender_id=1,
        chat_id=-1001,
        message_id=196001,
        received_at=datetime.now(UTC),
    )

    with patch.object(Path, "replace", replace_with_race):
        with pytest.raises(
            RuntimeError,
            match="DISPATCH_PERSISTENCE_VERIFY_FAILED",
        ):
            listener.process_remote_vps_signal(incoming)

    assert injected, "RACE_INJECTION_DID_NOT_EXECUTE"
    assert fake_http_client.sent_missions == [], (
        "HTTP_DISPATCH_OCCURRED_WITHOUT_DURABLE_MISSION"
    )

    restored_store = TelegramDispatchProgressStore(
        storage_path=storage,
    )

    assert restored_store.size() == 0, (
        "UNEXPECTED_DURABLE_MISSION_AFTER_FAILED_COMMIT"
    )
    assert store.size() == 0, (
        "UNVERIFIED_MISSION_REMAINED_IN_MEMORY"
    )
