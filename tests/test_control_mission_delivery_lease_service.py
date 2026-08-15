from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.trading.control.control_mission_delivery_lease_persistence import (
    ControlMissionDeliveryLeasePersistence,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)
from backend.trading.control.control_mission_delivery_lease_service import (
    ControlMissionDeliveryLeaseService,
)


FIXED_NOW = datetime(
    2026,
    8,
    15,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)


def build_service(
    *,
    registry: ControlMissionDeliveryLeaseRegistry | None = None,
    lease_seconds: float = 30.0,
    clock=lambda: FIXED_NOW,
    persistence: ControlMissionDeliveryLeasePersistence | None = None,
) -> ControlMissionDeliveryLeaseService:
    return ControlMissionDeliveryLeaseService(
        registry=(
            registry
            if registry is not None
            else ControlMissionDeliveryLeaseRegistry()
        ),
        lease_seconds=lease_seconds,
        clock=clock,
        persistence=persistence,
    )


def test_service_acquires_and_persists_lease(
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / "control_leases.json"
    persistence = ControlMissionDeliveryLeasePersistence(
        storage_path
    )
    registry = ControlMissionDeliveryLeaseRegistry()
    service = build_service(
        registry=registry,
        persistence=persistence,
    )

    lease = service.acquire(
        mission_id="control-001",
        agent_id="trusted-agent-001",
    )

    assert lease.leased_at == "2026-08-15T00:00:00Z"
    assert lease.expires_at == "2026-08-15T00:00:30Z"
    assert registry.get(
        "control-001"
    ) == lease

    restored = ControlMissionDeliveryLeaseRegistry()
    assert persistence.restore(
        restored
    ) == 1
    assert restored.get(
        "control-001"
    ) == lease


def test_same_agent_retry_returns_original_lease() -> None:
    registry = ControlMissionDeliveryLeaseRegistry()
    times = iter(
        [
            FIXED_NOW,
            FIXED_NOW + timedelta(seconds=10),
        ]
    )
    service = build_service(
        registry=registry,
        clock=lambda: next(times),
    )

    first = service.acquire(
        mission_id="control-001",
        agent_id="trusted-agent-001",
    )
    second = service.acquire(
        mission_id="control-001",
        agent_id="trusted-agent-001",
    )

    assert second == first
    assert registry.size() == 1


def test_different_agent_cannot_acquire_existing_lease() -> None:
    service = build_service()
    service.acquire(
        mission_id="control-001",
        agent_id="trusted-agent-001",
    )

    with pytest.raises(
        ValueError,
        match="already belongs to another Agent",
    ):
        service.acquire(
            mission_id="control-001",
            agent_id="trusted-agent-002",
        )


def test_service_normalizes_timezone_to_utc() -> None:
    local_time = datetime(
        2026,
        8,
        15,
        7,
        0,
        0,
        tzinfo=timezone(
            timedelta(hours=7)
        ),
    )
    service = build_service(
        clock=lambda: local_time
    )

    lease = service.acquire(
        mission_id="control-001",
        agent_id="trusted-agent-001",
    )

    assert lease.leased_at == "2026-08-15T00:00:00Z"
    assert lease.expires_at == "2026-08-15T00:00:30Z"


@pytest.mark.parametrize(
    (
        "lease_seconds",
        "error_type",
        "expected_message",
    ),
    [
        (
            "30",
            TypeError,
            "lease_seconds must be numeric",
        ),
        (
            0,
            ValueError,
            "lease_seconds must be greater than zero",
        ),
    ],
)
def test_service_rejects_invalid_lease_seconds(
    lease_seconds,
    error_type,
    expected_message: str,
) -> None:
    with pytest.raises(
        error_type,
        match=expected_message,
    ):
        build_service(
            lease_seconds=lease_seconds
        )


@pytest.mark.parametrize(
    (
        "clock",
        "error_type",
        "expected_message",
    ),
    [
        (
            lambda: "not-a-datetime",
            TypeError,
            "clock must return datetime",
        ),
        (
            lambda: datetime(2026, 8, 15),
            ValueError,
            "timezone-aware datetime",
        ),
    ],
)
def test_service_rejects_invalid_clock_result(
    clock,
    error_type,
    expected_message: str,
) -> None:
    service = build_service(
        clock=clock
    )

    with pytest.raises(
        error_type,
        match=expected_message,
    ):
        service.acquire(
            mission_id="control-001",
            agent_id="trusted-agent-001",
        )


def test_persistence_failure_rolls_back_new_lease(
    tmp_path: Path,
) -> None:
    class FailingPersistence(
        ControlMissionDeliveryLeasePersistence
    ):
        def save(self, registry) -> None:
            raise RuntimeError(
                "proof persistence failure"
            )

    registry = ControlMissionDeliveryLeaseRegistry()
    persistence = FailingPersistence(
        tmp_path / "control_leases.json"
    )
    service = build_service(
        registry=registry,
        persistence=persistence,
    )

    with pytest.raises(
        RuntimeError,
        match="proof persistence failure",
    ):
        service.acquire(
            mission_id="control-001",
            agent_id="trusted-agent-001",
        )

    assert registry.size() == 0