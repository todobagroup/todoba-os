from dataclasses import replace

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
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


def test_registry_registers_and_reads_record() -> None:
    registry = ControlMissionRegistry()
    record = ControlMissionRecord(
        mission=build_mission()
    )

    assert registry.register(
        record
    ) is record

    assert registry.get(
        "control-001"
    ) is record

    assert registry.list() == [
        record
    ]

    assert registry.size() == 1


def test_retry_does_not_reset_existing_lifecycle() -> None:
    registry = ControlMissionRegistry()
    mission = build_mission()

    existing = ControlMissionRecord(
        mission=mission,
        status=ControlMissionStatus.DELIVERED,
        delivered_at="2026-08-15T00:00:02Z",
    )

    registry.register(
        existing
    )

    retried = registry.register(
        ControlMissionRecord(
            mission=mission
        )
    )

    assert retried is existing
    assert retried.status is ControlMissionStatus.DELIVERED
    assert retried.delivered_at == "2026-08-15T00:00:02Z"


def test_same_id_with_different_payload_is_rejected() -> None:
    registry = ControlMissionRegistry()
    mission = build_mission()

    registry.register(
        ControlMissionRecord(
            mission=mission
        )
    )

    tampered = replace(
        mission,
        action=ControlAction.CLOSE_RED,
    )

    with pytest.raises(
        ValueError,
        match="different payload",
    ):
        registry.register(
            ControlMissionRecord(
                mission=tampered
            )
        )


def test_registry_removes_record() -> None:
    registry = ControlMissionRegistry()
    record = ControlMissionRecord(
        mission=build_mission()
    )

    registry.register(
        record
    )

    assert registry.remove(
        record.mission.mission_id
    ) is True

    assert registry.remove(
        record.mission.mission_id
    ) is False

    assert registry.size() == 0


def test_registry_rejects_wrong_record_type() -> None:
    registry = ControlMissionRegistry()

    with pytest.raises(
        TypeError,
        match="ControlMissionRecord",
    ):
        registry.register(
            "not-a-control-record"
        )