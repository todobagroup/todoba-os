"""
TODOBA Telegram Dispatch Recovery Tests

Proof:

Durable Telegram dispatch progress is recovered after
executor restart without rebuilding trading state.

Recovery rules:

- PENDING + valid + not expired:
  send the exact persisted mission and mark SUBMITTED.

- SUBMITTED:
  never send again.

- EXPIRED:
  never send again.

- PENDING + expired:
  mark EXPIRED and never send.

Recovery must not:
- read Broker State
- parse Telegram again
- recalculate position size
- rebuild mission payload
- extend mission expiry
"""

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
from backend.integrations.telegram_dispatch_recovery import (
    TelegramDispatchRecovery,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTarget,
    ExecutionTargetRegistry,
)


def build_target_registry() -> ExecutionTargetRegistry:
    registry = ExecutionTargetRegistry()

    registry.register(
        ExecutionTarget(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        )
    )

    registry.register(
        ExecutionTarget(
            agent_id="trusted-agent-002",
            account_fingerprint="account-b",
        )
    )

    return registry


def make_mission(
    *,
    agent_id: str,
    account_fingerprint: str,
    message_id: int,
    created_at: str,
    expires_at: str,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=(
            f"telegram-1001-{message_id}-"
            f"{agent_id}"
        ),
        agent_id=agent_id,
        account_fingerprint=(
            account_fingerprint
        ),
        symbol="XAUUSD",
        order_type="SELL NOW",
        volume=0.01,
        entry=None,
        sl=4380.0,
        tp=4340.0,
        magic_number=10001,
        comment="TODOBA",
        created_at=created_at,
        expires_at=expires_at,
        sequence=message_id,
        security_sequence=0,
    )


class FakeRemoteHttpClient:
    def __init__(self) -> None:
        self.sent_missions = []

    def send(
        self,
        mission: ExecutionMission,
    ) -> dict:
        self.sent_missions.append(
            mission
        )

        return {
            "status": "persisted",
            "mission_id": mission.mission_id,
        }


def build_recovery(
    *,
    tmp_path: Path,
    http_client: FakeRemoteHttpClient,
) -> tuple[
    TelegramDispatchRecovery,
    TelegramDispatchProgressStore,
]:
    store = TelegramDispatchProgressStore(
        storage_path=(
            tmp_path
            / "telegram_dispatch_progress.json"
        )
    )

    recovery = TelegramDispatchRecovery(
        progress_store=store,
        execution_target_registry=(
            build_target_registry()
        ),
        http_client=http_client,
        clock=lambda: datetime(
            2026,
            8,
            20,
            14,
            1,
            tzinfo=UTC,
        ),
    )

    return recovery, store


def test_pending_dispatch_is_recovered_with_exact_persisted_mission(
    tmp_path: Path,
) -> None:
    http_client = FakeRemoteHttpClient()

    recovery, store = build_recovery(
        tmp_path=tmp_path,
        http_client=http_client,
    )

    mission = make_mission(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        message_id=168601,
        created_at="2026-08-20T14:00:00Z",
        expires_at="2026-08-20T14:02:00Z",
    )

    store.prepare(
        chat_id=-1001,
        message_id=168601,
        mission=mission,
    )

    recovered_count = recovery.restore()

    assert recovered_count == 1

    assert http_client.sent_missions == [
        mission
    ]

    progress = store.get(
        chat_id=-1001,
        message_id=168601,
        agent_id="trusted-agent-001",
    )

    assert progress is not None

    assert progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    assert progress.mission == mission


def test_submitted_dispatch_is_not_sent_again(
    tmp_path: Path,
) -> None:
    http_client = FakeRemoteHttpClient()

    recovery, store = build_recovery(
        tmp_path=tmp_path,
        http_client=http_client,
    )

    mission = make_mission(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        message_id=168602,
        created_at="2026-08-20T14:00:00Z",
        expires_at="2026-08-20T14:02:00Z",
    )

    store.prepare(
        chat_id=-1001,
        message_id=168602,
        mission=mission,
    )

    store.mark_submitted(
        chat_id=-1001,
        message_id=168602,
        agent_id="trusted-agent-001",
    )

    recovered_count = recovery.restore()

    assert recovered_count == 0
    assert http_client.sent_missions == []

    progress = store.get(
        chat_id=-1001,
        message_id=168602,
        agent_id="trusted-agent-001",
    )

    assert progress is not None

    assert progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )


def test_expired_dispatch_is_not_sent_again(
    tmp_path: Path,
) -> None:
    http_client = FakeRemoteHttpClient()

    recovery, store = build_recovery(
        tmp_path=tmp_path,
        http_client=http_client,
    )

    mission = make_mission(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        message_id=168603,
        created_at="2026-08-20T13:00:00Z",
        expires_at="2026-08-20T13:02:00Z",
    )

    store.prepare(
        chat_id=-1001,
        message_id=168603,
        mission=mission,
    )

    store.mark_expired(
        chat_id=-1001,
        message_id=168603,
        agent_id="trusted-agent-001",
    )

    recovered_count = recovery.restore()

    assert recovered_count == 0
    assert http_client.sent_missions == []

    progress = store.get(
        chat_id=-1001,
        message_id=168603,
        agent_id="trusted-agent-001",
    )

    assert progress is not None

    assert progress.status == (
        TelegramDispatchStatus.EXPIRED
    )


def test_expired_pending_dispatch_is_marked_expired_without_send(
    tmp_path: Path,
) -> None:
    http_client = FakeRemoteHttpClient()

    recovery, store = build_recovery(
        tmp_path=tmp_path,
        http_client=http_client,
    )

    mission = make_mission(
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
        message_id=168604,
        created_at="2026-08-20T13:00:00Z",
        expires_at="2026-08-20T13:02:00Z",
    )

    store.prepare(
        chat_id=-1001,
        message_id=168604,
        mission=mission,
    )

    recovered_count = recovery.restore()

    assert recovered_count == 0
    assert http_client.sent_missions == []

    progress = store.get(
        chat_id=-1001,
        message_id=168604,
        agent_id="trusted-agent-002",
    )

    assert progress is not None

    assert progress.status == (
        TelegramDispatchStatus.EXPIRED
    )

    assert progress.mission == mission