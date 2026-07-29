import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)


def test_acknowledgement_store_push_pop():

    store = ExecutionMissionAcknowledgementStore()

    acknowledgement = ExecutionMissionAcknowledgement(
        mission_id="mission-001",
        agent_id="trusted-agent-001",
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-07-29T00:00:00Z",
    )

    store.push(
        acknowledgement
    )

    assert store.size() == 1

    result = store.pop()

    assert result == acknowledgement

    assert store.size() == 0


def test_acknowledgement_store_requires_acknowledgement():

    store = ExecutionMissionAcknowledgementStore()

    try:
        store.push("invalid")

        assert False

    except TypeError:
        assert True