from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_signing_payload import (
    ExecutionMissionSigningPayload,
)


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="proof081-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA",
        created_at="2026-08-08T16:00:00Z",
        expires_at="2099-01-01T00:00:00Z",
        sequence=1,
    )


def test_signing_payload_matches_fixed_cross_language_vector() -> None:
    mission = build_mission()

    payload = ExecutionMissionSigningPayload.build(
        mission
    )

    assert payload.decode(
        "utf-8"
    ) == (
        "12:proof081-001"
        "17:trusted-agent-001"
        "12:account-test"
        "6:XAUUSD"
        "3:BUY"
        "4:0.01"
        "4:null"
        "4:4100"
        "4:4200"
        "5:10001"
        "6:TODOBA"
        "20:2026-08-08T16:00:00Z"
        "20:2099-01-01T00:00:00Z"
        "1:1"
    )


def test_signing_payload_is_deterministic() -> None:
    mission = build_mission()

    first = ExecutionMissionSigningPayload.build(
        mission
    )

    second = ExecutionMissionSigningPayload.build(
        mission
    )

    assert first == second


def test_signing_payload_preserves_special_characters() -> None:
    mission = ExecutionMission(
        mission_id="proof081|special",
        agent_id="agent:001",
        account_fingerprint="account|test",
        symbol="GOLD.i#",
        order_type="BUY LIMIT",
        volume=0.05,
        entry=4099.5,
        sl=4080.0,
        tp=4150.0,
        magic_number=10001,
        comment="TODOBA|SAFE:MISSION",
        created_at="2026-08-08T16:00:00Z",
        expires_at="2099-01-01T00:00:00Z",
        sequence=2,
    )

    payload = ExecutionMissionSigningPayload.build(
        mission
    ).decode(
        "utf-8"
    )

    assert "16:proof081|special" in payload
    assert "9:agent:001" in payload
    assert "19:TODOBA|SAFE:MISSION" in payload