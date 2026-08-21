"""
TODOBA Telegram Dispatch Recovery Hardening Tests

CAP 3E proof:

Startup recovery must fail closed for invalid execution
targets and isolate recoverable dispatch failures so one
PENDING mission cannot block recovery of later missions.

Required rules:

- missing current execution target:
  mark INVALID_TARGET and never send

- changed account ownership:
  mark INVALID_TARGET and never send

- INVALID_TARGET is durable and terminal:
  do not resurrect even if the target later returns

- one send failure:
  keep that mission PENDING
  continue recovering later missions
  allow the exact persisted mission to retry later

Recovery must never:
- rebuild a mission
- change mission ownership
- extend mission expiry
- resend terminal dispatch progress
"""

from datetime import UTC
from datetime import datetime
from pathlib import Path

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


RECOVERY_TIME = datetime(
    2026,
    8,
    20,
    14,
    1,
    tzinfo=UTC,
)


def make_mission(
    *,
    agent_id: str,
    account_fingerprint: str,
    message_id: int,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=(
            f"telegram-hardening-{message_id}-"
            f"{agent_id}"
        ),
        agent_id=agent_id,
        account_fingerprint=account_fingerprint,
        symbol="XAUUSD",
        order_type="SELL NOW",
        volume=0.01,
        entry=None,
        sl=4380.0,
        tp=4340.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-08-20T14:00:00Z",
        expires_at="2026-08-20T14:05:00Z",
        sequence=message_id,
        security_sequence=0,
    )


def build_registry(
    *targets: tuple[str, str],
) -> ExecutionTargetRegistry:
    registry = ExecutionTargetRegistry()

    for agent_id, account_fingerprint in targets:
        registry.register(
            ExecutionTarget(
                agent_id=agent_id,
                account_fingerprint=account_fingerprint,
            )
        )

    return registry


class RecordingHttpClient:
    def __init__(
        self,
        *,
        failing_mission_ids: set[str] | None = None,
    ) -> None:
        self.failing_mission_ids = (
            set()
            if failing_mission_ids is None
            else set(failing_mission_ids)
        )
        self.sent_missions: list[
            ExecutionMission
        ] = []

    def send(
        self,
        mission: ExecutionMission,
    ) -> dict:
        self.sent_missions.append(
            mission
        )

        if (
            mission.mission_id
            in self.failing_mission_ids
        ):
            raise TimeoutError(
                "proof dispatch timeout"
            )

        return {
            "status": "persisted",
            "mission_id": mission.mission_id,
        }


def build_recovery(
    *,
    store: TelegramDispatchProgressStore,
    registry: ExecutionTargetRegistry,
    http_client: RecordingHttpClient,
) -> TelegramDispatchRecovery:
    return TelegramDispatchRecovery(
        progress_store=store,
        execution_target_registry=registry,
        http_client=http_client,
        clock=lambda: RECOVERY_TIME,
    )


def test_missing_target_is_durably_marked_invalid_without_send(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "telegram_dispatch_progress.json"
    )

    store = TelegramDispatchProgressStore(
        storage_path=storage_path
    )

    mission = make_mission(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        message_id=168701,
    )

    store.prepare(
        chat_id=-1001,
        message_id=168701,
        mission=mission,
    )

    http_client = RecordingHttpClient()

    recovery = build_recovery(
        store=store,
        registry=build_registry(),
        http_client=http_client,
    )

    recovered_count = recovery.restore()

    assert recovered_count == 0
    assert http_client.sent_missions == []

    progress = store.get(
        chat_id=-1001,
        message_id=168701,
        agent_id="trusted-agent-001",
    )

    assert progress is not None
    assert progress.status == (
        TelegramDispatchStatus.INVALID_TARGET
    )
    assert progress.mission == mission

    restored_store = TelegramDispatchProgressStore(
        storage_path=storage_path
    )

    restored_progress = restored_store.get(
        chat_id=-1001,
        message_id=168701,
        agent_id="trusted-agent-001",
    )

    assert restored_progress is not None
    assert restored_progress.status == (
        TelegramDispatchStatus.INVALID_TARGET
    )
    assert restored_progress.mission == mission


def test_changed_target_account_is_marked_invalid_without_send(
    tmp_path: Path,
) -> None:
    store = TelegramDispatchProgressStore(
        storage_path=(
            tmp_path
            / "telegram_dispatch_progress.json"
        )
    )

    mission = make_mission(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        message_id=168702,
    )

    store.prepare(
        chat_id=-1001,
        message_id=168702,
        mission=mission,
    )

    http_client = RecordingHttpClient()

    recovery = build_recovery(
        store=store,
        registry=build_registry(
            (
                "trusted-agent-001",
                "account-b",
            ),
        ),
        http_client=http_client,
    )

    recovered_count = recovery.restore()

    assert recovered_count == 0
    assert http_client.sent_missions == []

    progress = store.get(
        chat_id=-1001,
        message_id=168702,
        agent_id="trusted-agent-001",
    )

    assert progress is not None
    assert progress.status == (
        TelegramDispatchStatus.INVALID_TARGET
    )
    assert progress.mission == mission


def test_invalid_target_is_terminal_even_if_target_later_returns(
    tmp_path: Path,
) -> None:
    storage_path = (
        tmp_path
        / "telegram_dispatch_progress.json"
    )

    store = TelegramDispatchProgressStore(
        storage_path=storage_path
    )

    mission = make_mission(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        message_id=168703,
    )

    store.prepare(
        chat_id=-1001,
        message_id=168703,
        mission=mission,
    )

    first_client = RecordingHttpClient()

    first_recovery = build_recovery(
        store=store,
        registry=build_registry(),
        http_client=first_client,
    )

    assert first_recovery.restore() == 0
    assert first_client.sent_missions == []

    persisted_store = TelegramDispatchProgressStore(
        storage_path=storage_path
    )

    second_client = RecordingHttpClient()

    second_recovery = build_recovery(
        store=persisted_store,
        registry=build_registry(
            (
                "trusted-agent-001",
                "account-a",
            ),
        ),
        http_client=second_client,
    )

    recovered_count = second_recovery.restore()

    assert recovered_count == 0
    assert second_client.sent_missions == []

    progress = persisted_store.get(
        chat_id=-1001,
        message_id=168703,
        agent_id="trusted-agent-001",
    )

    assert progress is not None
    assert progress.status == (
        TelegramDispatchStatus.INVALID_TARGET
    )
    assert progress.mission == mission


def test_send_failure_stays_pending_and_does_not_block_later_dispatch(
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
        message_id=168704,
    )

    second_mission = make_mission(
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
        message_id=168705,
    )

    store.prepare(
        chat_id=-1001,
        message_id=168704,
        mission=first_mission,
    )

    store.prepare(
        chat_id=-1001,
        message_id=168705,
        mission=second_mission,
    )

    registry = build_registry(
        (
            "trusted-agent-001",
            "account-a",
        ),
        (
            "trusted-agent-002",
            "account-b",
        ),
    )

    failing_client = RecordingHttpClient(
        failing_mission_ids={
            first_mission.mission_id,
        }
    )

    first_recovery = build_recovery(
        store=store,
        registry=registry,
        http_client=failing_client,
    )

    recovered_count = first_recovery.restore()

    assert recovered_count == 1

    assert failing_client.sent_missions == [
        first_mission,
        second_mission,
    ]

    first_progress = store.get(
        chat_id=-1001,
        message_id=168704,
        agent_id="trusted-agent-001",
    )

    second_progress = store.get(
        chat_id=-1001,
        message_id=168705,
        agent_id="trusted-agent-002",
    )

    assert first_progress is not None
    assert second_progress is not None

    assert first_progress.status == (
        TelegramDispatchStatus.PENDING
    )

    assert second_progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    restarted_store = TelegramDispatchProgressStore(
        storage_path=storage_path
    )

    retry_client = RecordingHttpClient()

    retry_recovery = build_recovery(
        store=restarted_store,
        registry=registry,
        http_client=retry_client,
    )

    retry_count = retry_recovery.restore()

    assert retry_count == 1
    assert retry_client.sent_missions == [
        first_mission
    ]

    retried_progress = restarted_store.get(
        chat_id=-1001,
        message_id=168704,
        agent_id="trusted-agent-001",
    )

    already_submitted_progress = (
        restarted_store.get(
            chat_id=-1001,
            message_id=168705,
            agent_id="trusted-agent-002",
        )
    )

    assert retried_progress is not None
    assert already_submitted_progress is not None

    assert retried_progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )

    assert already_submitted_progress.status == (
        TelegramDispatchStatus.SUBMITTED
    )