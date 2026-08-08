from dataclasses import replace

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_signer import (
    ExecutionMissionSigner,
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