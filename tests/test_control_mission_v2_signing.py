from dataclasses import replace

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_signer_v2 import (
    ControlMissionSignerV2,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)


def build_mission() -> ControlMission:
    return ControlMission(
        mission_id="control-v2-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-a",
        action=ControlAction.CLOSE_GREEN,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-19T00:00:00Z",
        expires_at="2099-01-01T00:00:00Z",
        sequence=168001,
        security_sequence=42,
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


def test_control_v2_legacy_signing_secret_still_works() -> None:
    signer = ControlMissionSignerV2(
        "legacy-control-secret"
    )

    mission = build_mission()

    signature = signer.sign(
        mission
    )

    assert signer.verify(
        mission,
        signature,
    )


def test_control_v2_multi_agent_signer_uses_agent_specific_key() -> None:
    registry = build_signing_key_registry()

    signer = ControlMissionSignerV2(
        signing_key_registry=registry,
    )

    mission_a = build_mission()

    mission_b = replace(
        mission_a,
        mission_id="control-v2-002",
        agent_id="trusted-agent-002",
        account_fingerprint="account-b",
    )

    signature_a = signer.sign(
        mission_a
    )

    signature_b = signer.sign(
        mission_b
    )

    verifier_a = ControlMissionSignerV2(
        "control-key-a"
    )

    verifier_b = ControlMissionSignerV2(
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


def test_control_v2_multi_agent_signer_rejects_cross_agent_key() -> None:
    registry = build_signing_key_registry()

    signer = ControlMissionSignerV2(
        signing_key_registry=registry,
    )

    mission = build_mission()

    signature = signer.sign(
        mission
    )

    wrong_verifier = ControlMissionSignerV2(
        "control-key-b"
    )

    assert not wrong_verifier.verify(
        mission,
        signature,
    )


def test_control_v2_multi_agent_signer_rejects_unknown_agent() -> None:
    registry = build_signing_key_registry()

    signer = ControlMissionSignerV2(
        signing_key_registry=registry,
    )

    unknown_mission = replace(
        build_mission(),
        mission_id="control-v2-unknown",
        agent_id="unknown-agent",
    )

    with pytest.raises(
        ValueError,
        match="signing key not found",
    ):
        signer.sign(
            unknown_mission
        )


def test_control_v2_rejects_legacy_secret_and_registry_together() -> None:
    registry = build_signing_key_registry()

    with pytest.raises(
        ValueError,
        match="either",
    ):
        ControlMissionSignerV2(
            "legacy-control-secret",
            signing_key_registry=registry,
        )