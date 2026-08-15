from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_delivery_expiration_policy import (
    ControlMissionDeliveryExpirationPolicy,
)


def build_mission() -> ControlMission:
    return ControlMission(
        mission_id="control-001",
        agent_id="trusted-agent-001",
        account_fingerprint="account-test",
        action=ControlAction.FLATTEN_ALL,
        symbol="XAUUSD",
        magic_number=10001,
        requested_by_sender_id=5414928751,
        created_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:01:00Z",
        sequence=1,
    )


@pytest.mark.parametrize(
    (
        "current_time",
        "expected_expired",
    ),
    [
        (
            datetime(
                2026,
                8,
                15,
                0,
                0,
                59,
                tzinfo=timezone.utc,
            ),
            False,
        ),
        (
            datetime(
                2026,
                8,
                15,
                0,
                1,
                0,
                tzinfo=timezone.utc,
            ),
            True,
        ),
        (
            datetime(
                2026,
                8,
                15,
                0,
                1,
                1,
                tzinfo=timezone.utc,
            ),
            True,
        ),
    ],
)
def test_policy_evaluates_expiration_boundary(
    current_time: datetime,
    expected_expired: bool,
) -> None:
    policy = ControlMissionDeliveryExpirationPolicy()
    mission = build_mission()

    assert policy.is_expired(
        mission,
        current_time,
    ) is expected_expired
    assert policy.is_eligible(
        mission,
        current_time,
    ) is not expected_expired


def test_policy_normalizes_timezone_offset() -> None:
    policy = ControlMissionDeliveryExpirationPolicy()
    vietnam_time = datetime(
        2026,
        8,
        15,
        7,
        1,
        0,
        tzinfo=timezone(
            timedelta(hours=7)
        ),
    )

    assert policy.is_expired(
        build_mission(),
        vietnam_time,
    ) is True


def test_policy_treats_naive_current_time_as_utc() -> None:
    policy = ControlMissionDeliveryExpirationPolicy()
    naive_time = datetime(
        2026,
        8,
        15,
        0,
        0,
        59,
    )

    assert policy.is_eligible(
        build_mission(),
        naive_time,
    ) is True


def test_policy_rejects_invalid_mission() -> None:
    policy = ControlMissionDeliveryExpirationPolicy()

    with pytest.raises(
        TypeError,
        match="is_expired requires ControlMission",
    ):
        policy.is_expired(
            "not-a-control-mission",
            datetime.now(
                timezone.utc
            ),
        )


def test_policy_rejects_invalid_current_time() -> None:
    policy = ControlMissionDeliveryExpirationPolicy()

    with pytest.raises(
        TypeError,
        match="current_time must be datetime",
    ):
        policy.is_expired(
            build_mission(),
            "not-a-datetime",
        )