from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_serializer import (
    ExecutionMissionSerializer,
)


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="mission-001",
        agent_id="agent-demo-001",
        account_fingerprint="demo-account-001",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4120.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-07-28T00:00:00Z",
        expires_at="2026-07-28T00:01:00Z",
        sequence=1,
    )


def test_serialize_execution_mission():
    mission = build_mission()

    payload = ExecutionMissionSerializer.serialize(
        mission
    )

    assert payload == {
        "mission_id": "mission-001",
        "agent_id": "agent-demo-001",
        "account_fingerprint": "demo-account-001",
        "symbol": "XAUUSD",
        "order_type": "BUY",
        "volume": 0.01,
        "entry": None,
        "sl": 4100.0,
        "tp": 4120.0,
        "magic_number": 10001,
        "comment": "TODOBA",
        "created_at": "2026-07-28T00:00:00Z",
        "expires_at": "2026-07-28T00:01:00Z",
        "sequence": 1,
    }


def test_deserialize_execution_mission():
    mission = build_mission()

    payload = ExecutionMissionSerializer.serialize(
        mission
    )

    restored = ExecutionMissionSerializer.deserialize(
        payload
    )

    assert restored == mission


def test_serializer_rejects_invalid_types():
    try:
        ExecutionMissionSerializer.serialize(
            {"mission_id": "invalid"}
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "serialize must reject non-ExecutionMission."
        )

    try:
        ExecutionMissionSerializer.deserialize(
            "invalid"
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "deserialize must reject non-dict."
        )