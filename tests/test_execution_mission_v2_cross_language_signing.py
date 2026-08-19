from dataclasses import replace

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_signer_v2 import (
    ExecutionMissionSignerV2,
)
from backend.trading.execution.execution_mission_signing_payload_v2 import (
    ExecutionMissionSigningPayloadV2,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
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


def build_signing_key_registry(
) -> TrustedAgentSigningKeyRegistry:
    registry = TrustedAgentSigningKeyRegistry()

    registry.register(
        agent_id="trusted-agent-001",
        signing_secret="execution-key-a",
    )

    registry.register(
        agent_id="trusted-agent-002",
        signing_secret="execution-key-b",
    )

    return registry


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


def test_execution_v2_multi_agent_signer_uses_agent_specific_key():
    registry = build_signing_key_registry()

    signer = ExecutionMissionSignerV2(
        signing_key_registry=registry,
    )

    mission_a = build_mission()

    mission_b = replace(
        mission_a,
        mission_id="proof182-002",
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )

    signature_a = signer.sign(
        mission_a
    )

    signature_b = signer.sign(
        mission_b
    )

    verifier_a = ExecutionMissionSignerV2(
        "execution-key-a"
    )

    verifier_b = ExecutionMissionSignerV2(
        "execution-key-b"
    )

    assert verifier_a.verify(
        mission_a,
        signature_a,
    )

    assert verifier_b.verify(
        mission_b,
        signature_b,
    )


def test_execution_v2_multi_agent_signer_rejects_cross_agent_key():
    registry = build_signing_key_registry()

    signer = ExecutionMissionSignerV2(
        signing_key_registry=registry,
    )

    mission = build_mission()

    signature = signer.sign(
        mission
    )

    wrong_verifier = ExecutionMissionSignerV2(
        "execution-key-b"
    )

    assert not wrong_verifier.verify(
        mission,
        signature,
    )


def test_execution_v2_multi_agent_signer_rejects_unknown_agent():
    registry = build_signing_key_registry()

    signer = ExecutionMissionSignerV2(
        signing_key_registry=registry,
    )

    unknown_mission = replace(
        build_mission(),
        mission_id="proof182-unknown",
        agent_id="unknown-agent",
    )

    with pytest.raises(
        ValueError,
        match="signing key not found",
    ):
        signer.sign(
            unknown_mission
        )


def test_execution_v2_rejects_legacy_secret_and_registry_together():
    registry = build_signing_key_registry()

    with pytest.raises(
        ValueError,
        match="either",
    ):
        ExecutionMissionSignerV2(
            "legacy-secret",
            signing_key_registry=registry,
        )