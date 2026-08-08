from datetime import datetime
from datetime import timezone

import pytest

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_delivery_expiration_policy import (
    ExecutionMissionDeliveryExpirationPolicy,
)


def build_mission(
    *,
    expires_at: str,
) -> ExecutionMission:
    return ExecutionMission(
        mission_id="proof078-expiration-001",
        agent_id="trusted-agent-001",
        account_fingerprint="demo-account",
        symbol="XAUUSD",
        order_type="BUY",
        volume=0.01,
        entry=None,
        sl=4100.0,
        tp=4200.0,
        magic_number=10001,
        comment="TODOBA Proof078 Expiration",
        created_at="2026-08-08T12:00:00Z",
        expires_at=expires_at,
        sequence=1,
    )


def test_policy_allows_mission_before_expiration() -> None:
    policy = ExecutionMissionDeliveryExpirationPolicy()

    mission = build_mission(
        expires_at="2026-08-08T12:01:00Z"
    )

    current_time = datetime(
        2026,
        8,
        8,
        12,
        0,
        30,
        tzinfo=timezone.utc,
    )

    assert policy.is_expired(
        mission,
        current_time,
    ) is False

    assert policy.is_eligible(
        mission,
        current_time,
    ) is True


def test_policy_expires_mission_at_expiration_boundary() -> None:
    policy = ExecutionMissionDeliveryExpirationPolicy()

    mission = build_mission(
        expires_at="2026-08-08T12:01:00Z"
    )

    current_time = datetime(
        2026,
        8,
        8,
        12,
        1,
        0,
        tzinfo=timezone.utc,
    )

    assert policy.is_expired(
        mission,
        current_time,
    ) is True

    assert policy.is_eligible(
        mission,
        current_time,
    ) is False


def test_policy_expires_mission_after_expiration() -> None:
    policy = ExecutionMissionDeliveryExpirationPolicy()

    mission = build_mission(
        expires_at="2026-08-08T12:01:00Z"
    )

    current_time = datetime(
        2026,
        8,
        8,
        12,
        2,
        0,
        tzinfo=timezone.utc,
    )

    assert policy.is_expired(
        mission,
        current_time,
    ) is True


def test_policy_normalizes_timezone() -> None:
    policy = ExecutionMissionDeliveryExpirationPolicy()

    mission = build_mission(
        expires_at="2026-08-08T12:01:00Z"
    )

    current_time = datetime(
        2026,
        8,
        8,
        19,
        1,
        0,
        tzinfo=timezone.utc,
    ).astimezone(
        timezone.utc
    )

    assert policy.is_expired(
        mission,
        current_time,
    ) is True


def test_policy_rejects_invalid_expiration_timestamp() -> None:
    policy = ExecutionMissionDeliveryExpirationPolicy()

    mission = build_mission(
        expires_at="not-a-timestamp"
    )

    with pytest.raises(
        ValueError,
        match="expires_at must use ISO 8601 format.",
    ):
        policy.is_expired(
            mission,
            datetime.now(
                timezone.utc
            ),
        )