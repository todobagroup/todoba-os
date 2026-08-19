from dataclasses import replace

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_signer import (
    ExecutionMissionSigner,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)


def build_mission() -> ExecutionMission:
    return ExecutionMission(
        mission_id="proof080-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Proof080",
        created_at="2026-08-08T16:00:00Z",
        expires_at="2099-01-01T00:00:00Z",
        sequence=1,
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


def test_signing_same_mission_is_deterministic() -> None:
    signer = ExecutionMissionSigner(
        "proof080-signing-secret"
    )

    mission = build_mission()

    first = signer.sign(
        mission
    )

    second = signer.sign(
        mission
    )

    assert first == second
    assert len(first) == 64


def test_valid_signature_verifies() -> None:
    signer = ExecutionMissionSigner(
        "proof080-signing-secret"
    )

    mission = build_mission()

    signature = signer.sign(
        mission
    )

    assert signer.verify(
        mission,
        signature,
    )


def test_tampered_mission_does_not_verify() -> None:
    signer = ExecutionMissionSigner(
        "proof080-signing-secret"
    )

    mission = build_mission()

    signature = signer.sign(
        mission
    )

    tampered_mission = replace(
        mission,
        volume=1.0,
    )

    assert not signer.verify(
        tampered_mission,
        signature,
    )


def test_wrong_signing_secret_does_not_verify() -> None:
    signer = ExecutionMissionSigner(
        "proof080-signing-secret"
    )

    wrong_signer = ExecutionMissionSigner(
        "wrong-signing-secret"
    )

    mission = build_mission()

    signature = signer.sign(
        mission
    )

    assert not wrong_signer.verify(
        mission,
        signature,
    )


def test_empty_signing_secret_is_rejected() -> None:
    try:
        ExecutionMissionSigner(
            "   "
        )
    except ValueError as exc:
        assert str(exc) == (
            "signing_secret is required."
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )


def test_multi_agent_signer_uses_agent_specific_key() -> None:
    registry = build_signing_key_registry()

    signer = ExecutionMissionSigner(
        signing_key_registry=registry,
    )

    mission_a = build_mission()

    mission_b = replace(
        mission_a,
        mission_id="proof080-002",
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )

    signature_a = signer.sign(
        mission_a
    )

    signature_b = signer.sign(
        mission_b
    )

    verifier_a = ExecutionMissionSigner(
        "execution-key-a"
    )

    verifier_b = ExecutionMissionSigner(
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


def test_multi_agent_signer_rejects_cross_agent_key() -> None:
    registry = build_signing_key_registry()

    signer = ExecutionMissionSigner(
        signing_key_registry=registry,
    )

    mission_a = build_mission()

    signature_a = signer.sign(
        mission_a
    )

    wrong_verifier = ExecutionMissionSigner(
        "execution-key-b"
    )

    assert not wrong_verifier.verify(
        mission_a,
        signature_a,
    )


def test_multi_agent_signer_rejects_unknown_agent() -> None:
    registry = build_signing_key_registry()

    signer = ExecutionMissionSigner(
        signing_key_registry=registry,
    )

    unknown_mission = replace(
        build_mission(),
        mission_id="proof080-unknown",
        agent_id="unknown-agent",
    )

    with pytest.raises(
        ValueError,
        match="signing key not found",
    ):
        signer.sign(
            unknown_mission
        )


def test_signer_rejects_legacy_secret_and_registry_together() -> None:
    registry = build_signing_key_registry()

    with pytest.raises(
        ValueError,
        match="either",
    ):
        ExecutionMissionSigner(
            "legacy-secret",
            signing_key_registry=registry,
        )