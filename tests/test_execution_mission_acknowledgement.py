import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)


def test_execution_mission_acknowledgement_creation():

    acknowledgement = ExecutionMissionAcknowledgement(
        mission_id="mission-001",
        agent_id="trusted-agent-001",
        sequence=1,
        status="ACCEPTED",
        acknowledged_at="2026-07-29T00:00:00Z",
    )

    assert acknowledgement.mission_id == "mission-001"
    assert acknowledgement.agent_id == "trusted-agent-001"
    assert acknowledgement.sequence == 1
    assert acknowledgement.status == "ACCEPTED"