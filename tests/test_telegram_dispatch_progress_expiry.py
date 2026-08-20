"""
TODOBA Telegram Dispatch Progress Expiry Tests

Proof:

PENDING
-> EXPIRED

Expiration must be durable and idempotent.

A mission already confirmed SUBMITTED must never be
rewritten as EXPIRED by local retry logic.
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


def make_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id=(
            "telegram-1001-168301-"
            "trusted-agent-001"
        ),
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        symbol="XAUUSD",
        order_type="BUY NOW",
        volume=0.01,
        entry=None,
        sl=4300.0,
        tp=4400.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-08-20T14:00:00Z",
        expires_at="2026-08-20T14:02:00Z",
        sequence=168301,
        security_sequence=0,
    )


def make_store(
    tmp_path: Path,
) -> TelegramDispatchProgressStore:
    return TelegramDispatchProgressStore(
        storage_path=(
            tmp_path
            / "telegram_dispatch_progress.json"
        )
    )


def test_pending_progress_can_be_marked_expired_and_restored(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "telegram_dispatch_progress.json"
    )

    store = TelegramDispatchProgressStore(
        storage_path=storage_path
    )

    store.prepare(
        chat_id=-1001,
        message_id=168301,
        mission=make_mission(),
    )

    expired = store.mark_expired(
        chat_id=-1001,
        message_id=168301,
        agent_id="trusted-agent-001",
    )

    assert expired.status == (
        TelegramDispatchStatus.EXPIRED
    )

    restored_store = (
        TelegramDispatchProgressStore(
            storage_path=storage_path
        )
    )

    restored = restored_store.get(
        chat_id=-1001,
        message_id=168301,
        agent_id="trusted-agent-001",
    )

    assert restored is not None
    assert restored.status == (
        TelegramDispatchStatus.EXPIRED
    )
    assert restored.mission == (
        make_mission()
    )


def test_mark_expired_is_idempotent(
    tmp_path: Path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.prepare(
        chat_id=-1001,
        message_id=168301,
        mission=make_mission(),
    )

    first = store.mark_expired(
        chat_id=-1001,
        message_id=168301,
        agent_id="trusted-agent-001",
    )

    second = store.mark_expired(
        chat_id=-1001,
        message_id=168301,
        agent_id="trusted-agent-001",
    )

    assert first.status == (
        TelegramDispatchStatus.EXPIRED
    )
    assert second == first


def test_submitted_progress_cannot_be_marked_expired(
    tmp_path: Path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.prepare(
        chat_id=-1001,
        message_id=168301,
        mission=make_mission(),
    )

    store.mark_submitted(
        chat_id=-1001,
        message_id=168301,
        agent_id="trusted-agent-001",
    )

    with pytest.raises(
        ValueError,
        match="Submitted",
    ):
        store.mark_expired(
            chat_id=-1001,
            message_id=168301,
            agent_id="trusted-agent-001",
        )

    progress = store.get(
        chat_id=-1001,
        message_id=168301,
        agent_id="trusted-agent-001",
    )

    assert progress is not None
    assert progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )