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


def test_new_message_same_trade_intent_rejected_after_store_restart(
    tmp_path: Path,
) -> None:
    """A new Telegram ID cannot repeat a recent persisted trade intent."""
    from dataclasses import replace

    path = tmp_path / "telegram_dispatch_progress.json"

    first_store = TelegramDispatchProgressStore(
        storage_path=path,
    )

    first_mission = make_mission(
        created_at="2026-08-20T14:00:00Z",
        expires_at="2026-08-20T14:02:00Z",
    )

    first_store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=first_mission,
    )
    first_store.mark_submitted(
        chat_id=-1001,
        message_id=168201,
        agent_id=first_mission.agent_id,
    )

    restored_store = TelegramDispatchProgressStore(
        storage_path=path,
    )

    second_mission = replace(
        first_mission,
        mission_id="telegram-1001-168202-trusted-agent-001",
        sequence=168202,
        created_at="2026-08-20T14:00:10Z",
        expires_at="2026-08-20T14:02:10Z",
    )

    with pytest.raises(
        ValueError,
        match="DUPLICATE_TRADE_INTENT",
    ):
        restored_store.prepare(
            chat_id=-1001,
            message_id=168202,
            mission=second_mission,
        )

    assert restored_store.size() == 1


@pytest.mark.parametrize(
    ("delay_minutes", "should_block"),
    [
        (4, True),
        (11, False),
    ],
)
def test_trade_intent_dedup_time_boundary(
    tmp_path: Path,
    delay_minutes: int,
    should_block: bool,
) -> None:
    from dataclasses import replace
    from datetime import datetime, timedelta, timezone

    store = TelegramDispatchProgressStore(
        storage_path=tmp_path / "progress.json"
    )
    first = make_mission(
        created_at="2026-08-20T14:00:00Z",
        expires_at="2026-08-20T14:02:00Z",
    )
    store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=first,
    )
    store.mark_submitted(
        chat_id=-1001,
        message_id=168201,
        agent_id=first.agent_id,
    )

    later = datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc)
    later += timedelta(minutes=delay_minutes)
    second = replace(
        first,
        mission_id="telegram-1001-168202-trusted-agent-001",
        sequence=168202,
        created_at=later.isoformat(),
        expires_at=(later + timedelta(minutes=2)).isoformat(),
    )

    if should_block:
        with pytest.raises(ValueError, match="DUPLICATE_TRADE_INTENT"):
            store.prepare(
                chat_id=-1001, message_id=168202, mission=second
            )
        assert store.size() == 1
    else:
        store.prepare(
            chat_id=-1001, message_id=168202, mission=second
        )
        assert store.size() == 2


@pytest.mark.parametrize("change", ["different_tp", "different_account"])
def test_trade_intent_distinct_target_or_tp_is_allowed(
    tmp_path: Path,
    change: str,
) -> None:
    from dataclasses import replace

    store = TelegramDispatchProgressStore(
        storage_path=tmp_path / "progress.json"
    )
    first = make_mission(
        created_at="2026-08-20T14:00:00Z",
        expires_at="2026-08-20T14:02:00Z",
    )
    store.prepare(
        chat_id=-1001, message_id=168201, mission=first
    )
    store.mark_submitted(
        chat_id=-1001,
        message_id=168201,
        agent_id=first.agent_id,
    )

    changes = {
        "mission_id": "telegram-1001-168202-trusted-agent-001",
        "sequence": 168202,
        "created_at": "2026-08-20T14:00:10Z",
        "expires_at": "2026-08-20T14:02:10Z",
    }

    if change == "different_tp":
        changes["tp"] = 4350.0
    else:
        changes["account_fingerprint"] = "account-b"

    second = replace(first, **changes)
    store.prepare(
        chat_id=-1001, message_id=168202, mission=second
    )
    assert store.size() == 2


def test_independent_store_instances_preserve_both_missions(
    tmp_path: Path,
) -> None:
    """A stale writer must not erase another store instance's mission."""
    from dataclasses import replace

    path = tmp_path / "shared_dispatch_progress.json"

    store_a = TelegramDispatchProgressStore(storage_path=path)
    store_b = TelegramDispatchProgressStore(storage_path=path)

    mission_a = make_mission(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )

    mission_b = replace(
        make_mission(
            agent_id="trusted-agent-002",
            account_fingerprint="account-b",
        ),
        mission_id="telegram-1001-168202-trusted-agent-002",
        sequence=168202,
    )

    store_a.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=mission_a,
    )

    store_b.prepare(
        chat_id=-1001,
        message_id=168202,
        mission=mission_b,
    )

    restored = TelegramDispatchProgressStore(
        storage_path=path,
    )

    assert restored.get(
        chat_id=-1001,
        message_id=168201,
        agent_id="trusted-agent-001",
    ) is not None, "LOST_UPDATE_ERASED_FIRST_MISSION"

    assert restored.get(
        chat_id=-1001,
        message_id=168202,
        agent_id="trusted-agent-002",
    ) is not None, "LOST_UPDATE_ERASED_SECOND_MISSION"

    assert restored.size() == 2


def test_two_independent_processes_preserve_dispatch_missions(
    tmp_path: Path,
) -> None:
    """Two separate Python processes cannot erase each other's mission."""
    from dataclasses import asdict, replace
    import json
    import subprocess
    import time

    storage = tmp_path / "shared_progress.json"
    start_signal = tmp_path / "start.signal"
    worker_script = tmp_path / "dispatch_worker.py"

    worker_script.write_text(
        """
import json
from pathlib import Path
import sys
import time

# Worker script is inside pytest tmp_path, not the repo.
sys.path.insert(0, str(Path.cwd()))

from backend.integrations.telegram_dispatch_progress_store import (
    TelegramDispatchProgressStore,
)
from backend.trading.execution.execution_mission import ExecutionMission

storage = Path(sys.argv[1])
ready = Path(sys.argv[2])
start = Path(sys.argv[3])
chat_id = int(sys.argv[4])
message_id = int(sys.argv[5])
mission = ExecutionMission(**json.loads(sys.argv[6]))

store = TelegramDispatchProgressStore(storage_path=storage)
ready.write_text("READY", encoding="utf-8")

deadline = time.monotonic() + 12
while not start.exists():
    if time.monotonic() >= deadline:
        raise RuntimeError("WORKER_START_TIMEOUT")
    time.sleep(0.01)

store.prepare(
    chat_id=chat_id,
    message_id=message_id,
    mission=mission,
)
print("PREPARED", flush=True)
""".lstrip(),
        encoding="utf-8",
    )

    mission_a = make_mission(
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
    )
    mission_b = replace(
        make_mission(
            agent_id="trusted-agent-002",
            account_fingerprint="account-b",
        ),
        mission_id="telegram-1001-168202-trusted-agent-002",
        sequence=168202,
    )

    workers = []
    results = []

    try:
        for index, (message_id, mission) in enumerate(
            ((168201, mission_a), (168202, mission_b))
        ):
            ready = tmp_path / f"ready_{index}.signal"
            worker = subprocess.Popen(
                [
                    sys.executable,
                    str(worker_script),
                    str(storage),
                    str(ready),
                    str(start_signal),
                    "-1001",
                    str(message_id),
                    json.dumps(asdict(mission)),
                ],
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            workers.append(worker)

        deadline = time.monotonic() + 10
        while not all(
            (tmp_path / f"ready_{index}.signal").exists()
            for index in range(2)
        ):
            if time.monotonic() >= deadline:
                raise AssertionError("WORKERS_NOT_READY")
            exited = [
                worker for worker in workers
                if worker.poll() is not None
            ]
            if exited:
                diagnostics = [
                    worker.communicate(timeout=5)
                    for worker in exited
                ]
                raise AssertionError(
                    "WORKER_EXITED_BEFORE_START: "
                    + repr(diagnostics)
                )
            time.sleep(0.02)

        start_signal.write_text("START", encoding="utf-8")

        for worker in workers:
            stdout, stderr = worker.communicate(timeout=20)
            results.append((worker.returncode, stdout, stderr))

    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()
                worker.communicate(timeout=5)

    assert all(code == 0 for code, _, _ in results), (
        "CROSS_PROCESS_WORKER_FAILURE: " + repr(results)
    )

    restored = TelegramDispatchProgressStore(storage_path=storage)

    assert restored.get(
        chat_id=-1001,
        message_id=168201,
        agent_id="trusted-agent-001",
    ) is not None, "PROCESS_A_MISSION_LOST"

    assert restored.get(
        chat_id=-1001,
        message_id=168202,
        agent_id="trusted-agent-002",
    ) is not None, "PROCESS_B_MISSION_LOST"

    assert restored.size() == 2

@pytest.mark.parametrize(
    ("offset_seconds", "expect_block"),
    [
        (-660, True),
        (-10, True),
        (10, True),
        (660, False),
    ],
)
def test_trade_intent_rejects_backward_timestamps(
    tmp_path: Path,
    offset_seconds: int,
    expect_block: bool,
) -> None:
    """Clock rollback must not bypass semantic trade deduplication."""
    from dataclasses import replace
    from datetime import datetime, timedelta, timezone

    store = TelegramDispatchProgressStore(
        storage_path=tmp_path / "timestamp_guard.json",
    )

    first = make_mission(
        created_at="2026-08-20T14:00:00Z",
        expires_at="2026-08-20T14:02:00Z",
    )

    store.prepare(
        chat_id=-1001,
        message_id=168201,
        mission=first,
    )
    store.mark_submitted(
        chat_id=-1001,
        message_id=168201,
        agent_id=first.agent_id,
    )

    timestamp = datetime(
        2026, 8, 20, 14, 0, tzinfo=timezone.utc
    ) + timedelta(seconds=offset_seconds)

    second = replace(
        first,
        mission_id="telegram-1001-168202-trusted-agent-001",
        sequence=168202,
        created_at=timestamp.isoformat(),
        expires_at=(timestamp + timedelta(minutes=2)).isoformat(),
    )

    if expect_block:
        with pytest.raises(ValueError, match="DUPLICATE_TRADE_INTENT"):
            store.prepare(
                chat_id=-1001,
                message_id=168202,
                mission=second,
            )
        assert store.size() == 1
    else:
        store.prepare(
            chat_id=-1001,
            message_id=168202,
            mission=second,
        )
        assert store.size() == 2



def test_dispatch_store_rejects_real_ancestor_junction(
    tmp_path: Path,
) -> None:
    """A junction in any storage ancestor must fail before disk writes."""
    import os
    import subprocess

    if not hasattr(os.path, "isjunction"):
        pytest.skip("Windows junction detection unavailable")

    outside = tmp_path / "outside"
    nested = outside / "nested"
    nested.mkdir(parents=True)

    link = tmp_path / "redirect"
    script = tmp_path / "create_junction.ps1"

    script.write_text(
        """
param(
    [string]$Link,
    [string]$Target
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Junction -Path $Link -Target $Target `
    -ErrorAction Stop | Out-Null
""".lstrip(),
        encoding="utf-8",
    )

    creation = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            str(link),
            str(outside),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert creation.returncode == 0, (
        "TEST_JUNCTION_SETUP_FAILED: " + creation.stderr
    )
    assert os.path.isjunction(link)

    storage = link / "nested" / "progress.json"

    try:
        mission = make_mission()

        store = TelegramDispatchProgressStore(
            storage_path=storage,
        )

        with pytest.raises(
            RuntimeError,
            match="DISPATCH_LOCK_ANCESTOR_REPARSE_POINT",
        ):
            store.prepare(
                chat_id=-1001,
                message_id=168201,
                mission=mission,
            )

        assert not (nested / "progress.json").exists()
        assert not (nested / "progress.json.lock").exists()
        assert not (nested / "progress.json.tmp").exists()
        assert store.size() == 0

    finally:
        # Remove the junction entry only, never its target.
        if os.path.isjunction(link):
            link.rmdir()
        elif link.exists():
            raise RuntimeError(
                "TEST_JUNCTION_CHANGED_CLEANUP_REFUSED"
            )

def test_dispatch_store_rejects_preexisting_temp_hardlink(
    tmp_path: Path,
) -> None:
    """An existing .tmp hard link must never be overwritten or removed."""
    import os

    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

    sentinel = tmp_path / "sentinel.txt"
    original = b"TODOBA_HARDLINK_SENTINEL_MUST_REMAIN_UNCHANGED"
    sentinel.write_bytes(original)

    storage = storage_dir / "dispatch.json"
    temporary = storage.with_name(storage.name + ".tmp")

    os.link(sentinel, temporary)
    assert temporary.samefile(sentinel)

    store = TelegramDispatchProgressStore(
        storage_path=storage,
    )

    with pytest.raises(FileExistsError):
        store.prepare(
            chat_id=-1001,
            message_id=187001,
            mission=make_mission(),
        )

    assert sentinel.read_bytes() == original, (
        "HARDLINK_TARGET_CORRUPTED"
    )
    assert temporary.exists(), (
        "PREEXISTING_TEMP_FILE_WAS_REMOVED"
    )
    assert temporary.samefile(sentinel), (
        "PREEXISTING_HARDLINK_WAS_REPLACED"
    )
    assert not storage.exists(), (
        "MISSION_PERSISTED_DESPITE_UNSAFE_TEMP"
    )
    assert store.size() == 0

def test_dispatch_store_rejects_replaced_temp_before_commit(
    tmp_path: Path,
) -> None:
    """Do not acknowledge a mission absent from committed storage."""
    import json
    import os
    from unittest.mock import patch

    storage = tmp_path / "dispatch.json"
    temporary = tmp_path / "dispatch.json.tmp"
    replacement = tmp_path / "synthetic_replacement.json"
    replacement.write_text("[]", encoding="utf-8")

    store = TelegramDispatchProgressStore(
        storage_path=storage,
    )

    original_replace = Path.replace
    injected = False

    def replace_with_race(self, target):
        nonlocal injected

        if self == temporary and Path(target) == storage:
            assert self.exists()
            os.replace(replacement, temporary)
            injected = True

        return original_replace(self, target)

    with patch.object(Path, "replace", replace_with_race):
        with pytest.raises(
            RuntimeError,
            match="DISPATCH_PERSISTENCE_VERIFY_FAILED",
        ):
            store.prepare(
                chat_id=-1001,
                message_id=192001,
                mission=make_mission(),
            )

    assert injected, "REPLACEMENT_RACE_NOT_INJECTED"
    assert json.loads(storage.read_text(encoding="utf-8")) == []
    assert store.size() == 0, (
        "IN_MEMORY_MISSION_ACKNOWLEDGED_AFTER_FAILED_COMMIT"
    )

    restored = TelegramDispatchProgressStore(
        storage_path=storage,
    )
    assert restored.size() == 0
