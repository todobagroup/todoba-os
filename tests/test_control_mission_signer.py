from dataclasses import replace

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_signer import (
    ControlMissionSigner,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)


SIGNING_SECRET = "proof178-control-signing-secret"


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


def build_signing_key_registry(
) -> TrustedAgentSigningKeyRegistry:
    registry = TrustedAgentSigningKeyRegistry()

    registry.register(
        agent_id="trusted-agent-001",
        signing_secret="control-key-a",
    )

    registry.register(
        agent_id="trusted-agent-002",
        signing_secret="control-key-b",
    )

    return registry


def test_signing_matches_fixed_cross_language_vector() -> None:
    signature = ControlMissionSigner(
        SIGNING_SECRET
    ).sign(
        build_mission()
    )

    assert signature == (
        "187f7a4f52e51606e265b8c3fb0932cf"
        "97c2621c9397c0919059a83b83f73439"
    )


def test_valid_signature_verifies() -> None:
    signer = ControlMissionSigner(
        SIGNING_SECRET
    )

    mission = build_mission()

    assert signer.verify(
        mission,
        signer.sign(
            mission
        ),
    )


def test_tampered_action_does_not_verify() -> None:
    signer = ControlMissionSigner(
        SIGNING_SECRET
    )

    mission = build_mission()
    signature = signer.sign(
        mission
    )

    tampered = replace(
        mission,
        action=ControlAction.CLOSE_RED,
    )

    assert not signer.verify(
        tampered,
        signature,
    )


def test_tampered_sender_does_not_verify() -> None:
    signer = ControlMissionSigner(
        SIGNING_SECRET
    )

    mission = build_mission()
    signature = signer.sign(
        mission
    )

    tampered = replace(
        mission,
        requested_by_sender_id=320176245,
    )

    assert not signer.verify(
        tampered,
        signature,
    )


def test_wrong_signing_secret_does_not_verify() -> None:
    signer = ControlMissionSigner(
        SIGNING_SECRET
    )

    wrong_signer = ControlMissionSigner(
        "wrong-signing-secret"
    )

    mission = build_mission()

    assert not wrong_signer.verify(
        mission,
        signer.sign(
            mission
        ),
    )


def test_empty_signing_secret_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="signing_secret is required",
    ):
        ControlMissionSigner(
            "   "
        )


def test_multi_agent_signer_uses_agent_specific_key() -> None:
    registry = build_signing_key_registry()

    signer = ControlMissionSigner(
        signing_key_registry=registry,
    )

    mission_a = build_mission()

    mission_b = replace(
        mission_a,
        mission_id="control-002",
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )

    signature_a = signer.sign(
        mission_a
    )

    signature_b = signer.sign(
        mission_b
    )

    verifier_a = ControlMissionSigner(
        "control-key-a"
    )

    verifier_b = ControlMissionSigner(
        "control-key-b"
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

    signer = ControlMissionSigner(
        signing_key_registry=registry,
    )

    mission = build_mission()

    signature = signer.sign(
        mission
    )

    wrong_verifier = ControlMissionSigner(
        "control-key-b"
    )

    assert not wrong_verifier.verify(
        mission,
        signature,
    )


def test_multi_agent_signer_rejects_unknown_agent() -> None:
    registry = build_signing_key_registry()

    signer = ControlMissionSigner(
        signing_key_registry=registry,
    )

    unknown_mission = replace(
        build_mission(),
        mission_id="control-unknown",
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
        ControlMissionSigner(
            "legacy-secret",
            signing_key_registry=registry,
        )