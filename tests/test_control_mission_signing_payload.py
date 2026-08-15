from dataclasses import replace

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_signing_payload import (
    ControlMissionSigningPayload,
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


def test_signing_payload_matches_fixed_cross_language_vector() -> None:
    payload = ControlMissionSigningPayload.build(
        build_mission()
    )

    assert payload.decode(
        "utf-8"
    ) == (
        "25:TODOBA_CONTROL_MISSION_V1"
        "11:control-001"
        "17:trusted-agent-001"
        "12:account-test"
        "11:CLOSE_GREEN"
        "6:XAUUSD"
        "5:10001"
        "10:5414928751"
        "20:2026-08-15T00:00:00Z"
        "20:2026-08-15T00:01:00Z"
        "1:1"
    )


def test_signing_payload_is_deterministic() -> None:
    mission = build_mission()

    first = ControlMissionSigningPayload.build(
        mission
    )

    second = ControlMissionSigningPayload.build(
        mission
    )

    assert first == second


def test_signing_payload_binds_requesting_sender() -> None:
    mission = build_mission()

    other_sender = replace(
        mission,
        requested_by_sender_id=320176245,
    )

    assert ControlMissionSigningPayload.build(
        mission
    ) != ControlMissionSigningPayload.build(
        other_sender
    )


def test_signing_payload_rejects_wrong_contract() -> None:
    with pytest.raises(
        TypeError,
        match="requires ControlMission",
    ):
        ControlMissionSigningPayload.build(
            "not-a-control-mission"
        )