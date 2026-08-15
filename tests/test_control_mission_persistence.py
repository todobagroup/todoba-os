import json

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_persistence import (
    ControlMissionPersistence,
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


def test_persistence_saves_and_restores_repository(
    tmp_path,
) -> None:
    mission = build_mission()

    repository = ControlMissionRepository()
    repository.save(
        mission
    )

    storage_path = (
        tmp_path
        / "control_missions.json"
    )

    persistence = ControlMissionPersistence(
        storage_path
    )

    persistence.save(
        repository
    )

    restored_repository = (
        ControlMissionRepository()
    )

    assert persistence.restore(
        restored_repository
    ) == 1

    restored = restored_repository.get(
        mission.mission_id
    )

    assert restored == mission
    assert restored is not None
    assert restored.action is ControlAction.CLOSE_GREEN


def test_persistence_writes_json_network_contract(
    tmp_path,
) -> None:
    repository = ControlMissionRepository()
    repository.save(
        build_mission()
    )

    storage_path = (
        tmp_path
        / "control_missions.json"
    )

    ControlMissionPersistence(
        storage_path
    ).save(
        repository
    )

    payload = json.loads(
        storage_path.read_text(
            encoding="utf-8"
        )
    )

    assert payload[0]["action"] == "CLOSE_GREEN"
    assert payload[0]["requested_by_sender_id"] == (
        5414928751
    )


def test_persistence_replaces_temporary_file(
    tmp_path,
) -> None:
    repository = ControlMissionRepository()
    repository.save(
        build_mission()
    )

    storage_path = (
        tmp_path
        / "control_missions.json"
    )

    ControlMissionPersistence(
        storage_path
    ).save(
        repository
    )

    temporary_path = storage_path.with_suffix(
        storage_path.suffix + ".tmp"
    )

    assert storage_path.exists()
    assert not temporary_path.exists()


def test_restore_missing_file_returns_zero(
    tmp_path,
) -> None:
    persistence = ControlMissionPersistence(
        tmp_path
        / "missing-control-missions.json"
    )

    assert persistence.restore(
        ControlMissionRepository()
    ) == 0