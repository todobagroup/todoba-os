import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_serializer import (
    ControlMissionSerializer,
)


def build_mission() -> ControlMission:
    return ControlMission(
        mission_id="control-001",
        agent_id="agent-demo-001",
        account_fingerprint="demo-account-001",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:01:00Z",
        sequence=1,
    )


def test_serialize_control_mission() -> None:
    payload = ControlMissionSerializer.serialize(
        build_mission()
    )

    assert payload == {
        "mission_id": "control-001",
        "agent_id": "agent-demo-001",
        "account_fingerprint": "demo-account-001",
        "action": "CLOSE_GREEN",
        "symbol": "XAUUSD",
        "magic_number": 10001,
        "requested_by_sender_id": 5414928751,
        "created_at": "2026-08-15T00:00:00Z",
        "expires_at": "2026-08-15T00:01:00Z",
        "sequence": 1,
    }


def test_deserialize_control_mission() -> None:
    mission = build_mission()

    restored = ControlMissionSerializer.deserialize(
        ControlMissionSerializer.serialize(
            mission
        )
    )

    assert restored == mission
    assert restored.action is ControlAction.CLOSE_GREEN


def test_serializer_rejects_invalid_types() -> None:
    with pytest.raises(
        TypeError,
        match="serialize requires ControlMission",
    ):
        ControlMissionSerializer.serialize(
            {"mission_id": "invalid"}
        )

    with pytest.raises(
        TypeError,
        match="deserialize requires dict",
    ):
        ControlMissionSerializer.deserialize(
            "invalid"
        )


def test_deserializer_rejects_unknown_action() -> None:
    payload = ControlMissionSerializer.serialize(
        build_mission()
    )

    payload["action"] = "UNKNOWN_CONTROL_ACTION"

    with pytest.raises(ValueError):
        ControlMissionSerializer.deserialize(
            payload
        )