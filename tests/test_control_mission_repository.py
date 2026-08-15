from dataclasses import replace

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
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


def test_repository_stores_and_reads_mission() -> None:
    repository = ControlMissionRepository()
    mission = build_mission()

    assert repository.save(
        mission
    ) == mission

    assert repository.get(
        mission.mission_id
    ) == mission

    assert repository.all() == [
        mission
    ]

    assert repository.size() == 1


def test_repository_removes_existing_mission() -> None:
    repository = ControlMissionRepository()
    mission = build_mission()

    repository.save(
        mission
    )

    assert repository.remove(
        mission.mission_id
    ) is True

    assert repository.get(
        mission.mission_id
    ) is None

    assert repository.size() == 0


def test_repository_remove_missing_returns_false() -> None:
    repository = ControlMissionRepository()

    assert repository.remove(
        "missing-control"
    ) is False


def test_same_mission_retry_is_idempotent() -> None:
    repository = ControlMissionRepository()
    mission = build_mission()

    first = repository.save(
        mission
    )
    second = repository.save(
        mission
    )

    assert first is mission
    assert second is mission
    assert repository.size() == 1


def test_same_id_with_different_payload_is_rejected() -> None:
    repository = ControlMissionRepository()
    mission = build_mission()

    repository.save(
        mission
    )

    tampered = replace(
        mission,
        action=ControlAction.CLOSE_RED,
    )

    with pytest.raises(
        ValueError,
        match="different payload",
    ):
        repository.save(
            tampered
        )


def test_repository_rejects_wrong_contract() -> None:
    repository = ControlMissionRepository()

    with pytest.raises(
        TypeError,
        match="save requires ControlMission",
    ):
        repository.save(
            "not-a-control-mission"
        )