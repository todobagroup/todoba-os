from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)


def build_mission() -> ControlMission:
    return ControlMission(
        mission_id="control-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:01:00Z",
        sequence=1,
    )


def test_control_mission_record_defaults() -> None:
    mission = build_mission()
    record = ControlMissionRecord(
        mission=mission
    )

    assert record.mission == mission
    assert record.status is ControlMissionStatus.CREATED

    assert record.delivered_at is None
    assert record.delivery_attempt_count == 0
    assert record.acknowledged_at is None
    assert record.started_at is None
    assert record.completed_at is None
    assert record.failed_at is None
    assert record.failure_reason is None

    assert record.matched_position_count == 0
    assert record.closed_position_count == 0
    assert record.matched_pending_order_count == 0
    assert record.canceled_pending_order_count == 0
    assert record.failed_item_count == 0


def test_control_record_tracks_result_outside_mission() -> None:
    mission = build_mission()
    record = ControlMissionRecord(
        mission=mission
    )

    record.status = ControlMissionStatus.COMPLETED
    record.completed_at = "2026-08-15T00:00:05Z"
    record.matched_position_count = 3
    record.closed_position_count = 3

    assert record.mission is mission
    assert mission.action is ControlAction.CLOSE_GREEN
    assert record.status is ControlMissionStatus.COMPLETED
    assert record.closed_position_count == 3