from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)


def test_control_mission_status_values() -> None:
    assert [
        status.value
        for status in ControlMissionStatus
    ] == [
        "CREATED",
        "QUEUED",
        "DELIVERED",
        "ACKNOWLEDGED",
        "EXECUTING",
        "COMPLETED",
        "FAILED",
    ]