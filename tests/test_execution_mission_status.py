import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


def test_execution_mission_status_values():

    assert (
        ExecutionMissionStatus.CREATED.value
        == "CREATED"
    )

    assert (
        ExecutionMissionStatus.QUEUED.value
        == "QUEUED"
    )

    assert (
        ExecutionMissionStatus.DELIVERED.value
        == "DELIVERED"
    )

    assert (
        ExecutionMissionStatus.ACKNOWLEDGED.value
        == "ACKNOWLEDGED"
    )

    assert (
        ExecutionMissionStatus.EXECUTING.value
        == "EXECUTING"
    )

    assert (
        ExecutionMissionStatus.COMPLETED.value
        == "COMPLETED"
    )

    assert (
        ExecutionMissionStatus.FAILED.value
        == "FAILED"
    )