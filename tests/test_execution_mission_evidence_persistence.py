import json
from pathlib import Path
from threading import Event
from threading import Thread
from threading import current_thread

import pytest

import backend.trading.execution.execution_mission_evidence_persistence as evidence_persistence_module

from backend.trading.execution.broker_execution_evidence import (
    BrokerExecutionEvidence,
)
from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_completed import (
    ExecutionMissionCompleted,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)
from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)
from backend.trading.execution.execution_mission_failed import (
    ExecutionMissionFailed,
)
from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


AGENT_ID = "agent-001"


def build_stores():
    return {
        "acknowledgement_store": (
            ExecutionMissionAcknowledgementStore()
        ),
        "execution_started_store": (
            ExecutionMissionExecutionStartedStore()
        ),
        "completed_store": (
            ExecutionMissionCompletedStore()
        ),
        "failed_store": (
            ExecutionMissionFailedStore()
        ),
        "broker_evidence_store": (
            BrokerExecutionEvidenceStore()
        ),
    }


def build_mission(
    mission_id: str,
    sequence: int,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id=mission_id,
        agent_id=AGENT_ID,
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4000.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA evidence persistence",
        sequence=sequence,
        created_at="2026-08-07T00:00:00Z",
        expires_at="2026-08-07T00:05:00Z",
    )


def build_mission_registry() -> ExecutionMissionRegistry:
    mission_registry = ExecutionMissionRegistry()

    for sequence, mission_id in enumerate(
        (
            "mission-001",
            "mission-002",
            "mission-003",
            "mission-004",
            "mission-005",
        ),
        start=1,
    ):
        mission_registry.register(
            ExecutionMissionRecord(
                mission=build_mission(
                    mission_id=mission_id,
                    sequence=sequence,
                )
            )
        )

    return mission_registry


def test_persistence_saves_and_restores_all_evidence_types(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    acknowledgement = ExecutionMissionAcknowledgement(
        mission_id="mission-001",
        agent_id=AGENT_ID,
        sequence=1,
        status="ACKNOWLEDGED",
        acknowledged_at="2026-08-07T00:00:01Z",
    )

    execution_started = ExecutionMissionExecutionStarted(
        mission_id="mission-002",
        agent_id=AGENT_ID,
        sequence=2,
        started_at="2026-08-07T00:00:02Z",
    )

    completed = ExecutionMissionCompleted(
        mission_id="mission-003",
        agent_id=AGENT_ID,
        sequence=3,
        completed_at="2026-08-07T00:00:03Z",
    )

    failed = ExecutionMissionFailed(
        mission_id="mission-004",
        agent_id=AGENT_ID,
        sequence=4,
        failed_at="2026-08-07T00:00:04Z",
        failure_reason="broker rejected order",
    )

    broker_evidence = BrokerExecutionEvidence(
        mission_id="mission-005",
        agent_id=AGENT_ID,
        success=True,
        retcode=10009,
        order_ticket=123456,
        deal_ticket=654321,
        execution_price=4105.5,
        comment="executed",
        completed_at="2026-08-07T00:00:05Z",
    )

    evidence = [
        acknowledgement,
        execution_started,
        completed,
        failed,
        broker_evidence,
    ]

    for item in evidence:
        persistence.save(
            item
        )

    assert persistence.size() == 5

    stores = build_stores()

    mission_registry = build_mission_registry()

    restored = persistence.restore(
        **stores,
        mission_registry=mission_registry,
    )

    assert restored == 5

    assert (
        stores["acknowledgement_store"].pop()
        == acknowledgement
    )

    assert (
        stores["execution_started_store"].pop()
        == execution_started
    )

    assert (
        stores["completed_store"].pop()
        == completed
    )

    assert (
        stores["failed_store"].pop()
        == failed
    )

    assert (
        stores["broker_evidence_store"].pop()
        == broker_evidence
    )


def test_persistence_remove_removes_processed_evidence(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    evidence = ExecutionMissionCompleted(
        mission_id="mission-remove",
        agent_id=AGENT_ID,
        sequence=1,
        completed_at="2026-08-07T00:00:00Z",
    )

    persistence.save(
        evidence
    )

    assert persistence.size() == 1

    removed = persistence.remove(
        evidence
    )

    assert removed is True
    assert persistence.size() == 0


def test_persistence_remove_missing_evidence_returns_false(
    tmp_path: Path,
) -> None:
    persistence = ExecutionMissionEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    evidence = ExecutionMissionFailed(
        mission_id="mission-missing",
        agent_id=AGENT_ID,
        sequence=1,
        failed_at="2026-08-07T00:00:00Z",
        failure_reason="test",
    )

    removed = persistence.remove(
        evidence
    )

    assert removed is False
    assert persistence.size() == 0


class CoordinatedEvidencePersistence(
    ExecutionMissionEvidencePersistence
):
    def __init__(
        self,
        storage_path: Path,
    ) -> None:
        super().__init__(
            storage_path
        )

        self.first_read_complete = Event()
        self.release_first_read = Event()
        self.second_write_complete = Event()

    def _read_payload(self):
        payload = super()._read_payload()

        if current_thread().name == "first-save":
            self.first_read_complete.set()

            if not self.release_first_read.wait(
                timeout=5.0
            ):
                raise TimeoutError(
                    "Timed out waiting to release first read."
                )

        return payload

    def _write_payload(
        self,
        payload,
    ) -> None:
        super()._write_payload(
            payload
        )

        if current_thread().name == "second-save":
            self.second_write_complete.set()


def test_persistence_serializes_concurrent_read_modify_write(
    tmp_path: Path,
) -> None:
    persistence = CoordinatedEvidencePersistence(
        tmp_path / "execution_mission_evidence.json"
    )

    first = ExecutionMissionCompleted(
        mission_id="mission-concurrent-001",
        agent_id=AGENT_ID,
        sequence=1,
        completed_at="2026-08-07T00:00:01Z",
    )

    second = ExecutionMissionCompleted(
        mission_id="mission-concurrent-002",
        agent_id=AGENT_ID,
        sequence=2,
        completed_at="2026-08-07T00:00:02Z",
    )

    failures = []

    def save_evidence(evidence):
        try:
            persistence.save(
                evidence
            )
        except Exception as exc:
            failures.append(
                exc
            )

    first_thread = Thread(
        target=save_evidence,
        args=(first,),
        name="first-save",
    )

    second_thread = Thread(
        target=save_evidence,
        args=(second,),
        name="second-save",
    )

    first_thread.start()

    assert persistence.first_read_complete.wait(
        timeout=2.0
    )

    second_thread.start()

    second_finished_before_release = (
        persistence.second_write_complete.wait(
            timeout=0.5
        )
    )

    persistence.release_first_read.set()

    first_thread.join(
        timeout=5.0
    )

    second_thread.join(
        timeout=5.0
    )

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert failures == []

    assert second_finished_before_release is False

    payload = json.loads(
        persistence.storage_path.read_text(
            encoding="utf-8"
        )
    )

    mission_ids = {
        item["payload"]["mission_id"]
        for item in payload
    }

    assert mission_ids == {
        "mission-concurrent-001",
        "mission-concurrent-002",
    }


def test_persistence_failed_atomic_replace_preserves_previous_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_path = (
        tmp_path / "execution_mission_evidence.json"
    )

    persistence = ExecutionMissionEvidencePersistence(
        storage_path
    )

    first = ExecutionMissionCompleted(
        mission_id="mission-atomic-001",
        agent_id=AGENT_ID,
        sequence=1,
        completed_at="2026-08-07T00:00:01Z",
    )

    second = ExecutionMissionCompleted(
        mission_id="mission-atomic-002",
        agent_id=AGENT_ID,
        sequence=2,
        completed_at="2026-08-07T00:00:02Z",
    )

    persistence.save(
        first
    )

    previous_bytes = storage_path.read_bytes()

    def fail_replace(
        source,
        destination,
    ):
        raise OSError(
            "simulated atomic replace failure"
        )

    monkeypatch.setattr(
        evidence_persistence_module.os,
        "replace",
        fail_replace,
    )

    with pytest.raises(
        OSError,
        match="simulated atomic replace failure",
    ):
        persistence.save(
            second
        )

    assert storage_path.read_bytes() == previous_bytes

    payload = json.loads(
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert len(payload) == 1

    assert (
        payload[0]["payload"]["mission_id"]
        == "mission-atomic-001"
    )

    temporary_files = list(
        tmp_path.glob(
            ".execution_mission_evidence.json.*.tmp"
        )
    )

    assert temporary_files == []
