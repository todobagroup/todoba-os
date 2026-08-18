from dataclasses import replace

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_signer_v2 import (
    ExecutionMissionSignerV2,
)
from backend.trading.execution.execution_mission_signing_payload_v2 import (
    ExecutionMissionSigningPayloadV2,
)


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="proof182-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        symbol="XAUUSD",
        order_type="BUY LIMIT",
        volume=0.05,
        entry=4099.5,
        sl=4080.0,
        tp=4150.0,
        magic_number=10001,
        comment="TODOBA|V2",
        created_at="2026-08-18T02:00:00Z",
        expires_at="2099-01-01T00:00:00Z",
        sequence=168001,
        security_sequence=42,
    )


def test_execution_v2_signing_payload_matches_fixed_cross_language_vector():
    mission = build_mission()

    payload = (
        ExecutionMissionSigningPayloadV2.build(
            mission
        )
    )

    assert payload.decode(
        "utf-8"
    ) == (
        "27:TODOBA_EXECUTION_MISSION_V2"
        "12:proof182-001"
        "17:trusted-agent-001"
        "12:account-test"
        "6:XAUUSD"
        "9:BUY LIMIT"
        "4:0.05"
        "6:4099.5"
        "4:4080"
        "4:4150"
        "5:10001"
        "9:TODOBA|V2"
        "20:2026-08-18T02:00:00Z"
        "20:2099-01-01T00:00:00Z"
        "6:168001"
        "2:42"
    )


def test_execution_v2_hmac_matches_fixed_cross_language_vector():
    mission = build_mission()

    signer = ExecutionMissionSignerV2(
        "proof182-secret"
    )

    signature = signer.sign(
        mission
    )

    assert signature == (
        "d264045fb230dfc316ad6b8c50228b36"
        "c1043753360ef46c9805efab1da57a0d"
    )

    assert signer.verify(
        mission,
        signature,
    )


def test_execution_v2_signature_binds_security_sequence():
    mission = build_mission()

    replay_variant = replace(
        mission,
        security_sequence=43,
    )

    signer = ExecutionMissionSignerV2(
        "proof182-secret"
    )

    assert signer.sign(
        mission
    ) != signer.sign(
        replay_variant
    )