import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_mission_execution_started import (
    ExecutionMissionExecutionStarted,
)


def test_execution_mission_execution_started_creation():

    evidence = ExecutionMissionExecutionStarted(
        mission_id="execution-start-001",
        agent_id="trusted-agent-001",
        sequence=1,
        started_at="2026-07-29T00:20:00",
    )

    assert evidence.mission_id == (
        "execution-start-001"
    )

    assert evidence.agent_id == (
        "trusted-agent-001"
    )

    assert evidence.sequence == 1

    assert evidence.started_at == (
        "2026-07-29T00:20:00"
    )