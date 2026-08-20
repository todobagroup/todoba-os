"""
TODOBA Telegram Dispatch Progress Store Tests

Proof:

Telegram source + execution target
->
exact immutable ExecutionMission
->
durable dispatch progress

The store must preserve the exact mission payload so a
retry never rebuilds a mission from new broker state,
timestamps, or sizing data.
"""

import sys
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


def make_mission(
    *,
    agent_id: str = "trusted-agent-001",
    account_fingerprint: str = "account-a",
    volume: float = 0.01,
    created_at: str = "2026-08-20T14:00:00Z",
    expires_at: str = "2026-08-20T14:02:00Z",
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=(
            "telegram-1001-168201-"
            f"{agent_id}"
        ),
        agent_id=agent_id,
        account_fingerprint=(
            account_fingerprint
        ),
        symbol="XAUUSD",
        order_type="SELL NOW",
        volume=volume,
        entry=None,
        sl=4380.0,
        tp=4340.0,
        magic_number=10001,
        comment="TODOBA",
        created_at=created_at,
        expires_at=expires_at,
        sequence=168201,
        security_sequence=0,
    )


def test_prepare_target_creates_pending_progress(
    tmp_path: Path,
) -> None:
    store = TelegramDispatchProgressStore(
        storage_path=(
            tmp_path
            / "telegram_dispatch_progress.json"
        )
    )

    mission = make_mission()

    progress = store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=mission,
    )

    assert progress.chat_id == -1001
    assert progress.message_id == 168201
    assert progress.agent_id == (
        "trusted-agent-001"
    )
    assert progress.status == (
        TelegramDispatchStatus.PENDING
    )
    assert progress.mission == mission
    assert store.size() == 1


def test_prepare_preserves_exact_execution_mission(
    tmp_path: Path,
) -> None:
    store = TelegramDispatchProgressStore(
        storage_path=(
            tmp_path
            / "telegram_dispatch_progress.json"
        )
    )

    mission = make_mission(
        volume=0.03,
        created_at="2026-08-20T14:00:17Z",
        expires_at="2026-08-20T14:02:17Z",
    )

    store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=mission,
    )

    stored = store.get(
        chat_id=-1001,
        message_id=168201,
        agent_id="trusted-agent-001",
    )

    assert stored is not None
    assert stored.mission == mission
    assert (
        stored.mission.created_at
        == "2026-08-20T14:00:17Z"
    )
    assert (
        stored.mission.expires_at
        == "2026-08-20T14:02:17Z"
    )
    assert stored.mission.volume == 0.03


def test_prepare_same_source_target_and_same_mission_is_idempotent(
    tmp_path: Path,
) -> None:
    store = TelegramDispatchProgressStore(
        storage_path=(
            tmp_path
            / "telegram_dispatch_progress.json"
        )
    )

    mission = make_mission()

    first = store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=mission,
    )

    second = store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=mission,
    )

    assert second == first
    assert store.size() == 1


def test_prepare_same_source_target_with_different_mission_rejects_conflict(
    tmp_path: Path,
) -> None:
    store = TelegramDispatchProgressStore(
        storage_path=(
            tmp_path
            / "telegram_dispatch_progress.json"
        )
    )

    store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=make_mission(
            volume=0.01,
        ),
    )

    with pytest.raises(
        ValueError,
        match="dispatch progress conflict",
    ):
        store.prepare(
            chat_id=-1001,
            message_id=168201,
            mission=make_mission(
                volume=0.02,
            ),
        )


def test_mark_submitted_is_durable(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "telegram_dispatch_progress.json"
    )

    store = TelegramDispatchProgressStore(
        storage_path=storage_path
    )

    mission = make_mission()

    store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=mission,
    )

    submitted = store.mark_submitted(
        chat_id=-1001,
        message_id=168201,
        agent_id="trusted-agent-001",
    )

    assert submitted.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    restored_store = (
        TelegramDispatchProgressStore(
            storage_path=storage_path
        )
    )

    restored = restored_store.get(
        chat_id=-1001,
        message_id=168201,
        agent_id="trusted-agent-001",
    )

    assert restored is not None
    assert restored.status == (
        TelegramDispatchStatus.SUBMITTED
    )
    assert restored.mission == mission


def test_restart_restores_pending_and_submitted_targets(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "telegram_dispatch_progress.json"
    )

    store = TelegramDispatchProgressStore(
        storage_path=storage_path
    )

    first_mission = make_mission(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        volume=0.01,
    )

    second_mission = make_mission(
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
        volume=0.02,
    )

    store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=first_mission,
    )

    store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=second_mission,
    )

    store.mark_submitted(
        chat_id=-1001,
        message_id=168201,
        agent_id="trusted-agent-001",
    )

    restored_store = (
        TelegramDispatchProgressStore(
            storage_path=storage_path
        )
    )

    first_progress = restored_store.get(
        chat_id=-1001,
        message_id=168201,
        agent_id="trusted-agent-001",
    )

    second_progress = restored_store.get(
        chat_id=-1001,
        message_id=168201,
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
        == first_mission
    )

    assert (
        second_progress.mission
        == second_mission
    )

    assert restored_store.size() == 2