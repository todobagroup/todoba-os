import json
from pathlib import Path

import pytest

from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
)
from backend.trading.control.control_mission_delivery_lease_persistence import (
    ControlMissionDeliveryLeasePersistence,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)


def build_lease(
    *,
    mission_id: str = "control-001",
) -> ControlMissionDeliveryLease:
    return ControlMissionDeliveryLease(
        mission_id=mission_id,
        agent_id="trusted-agent-001",
        leased_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:00:30Z",
    )


def test_persistence_saves_and_restores_active_leases(
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / "control_leases.json"
    persistence = ControlMissionDeliveryLeasePersistence(
        storage_path
    )
    registry = ControlMissionDeliveryLeaseRegistry()
    first = build_lease()
    second = build_lease(
        mission_id="control-002"
    )
    registry.acquire(
        first
    )
    registry.acquire(
        second
    )

    persistence.save(
        registry
    )

    assert storage_path.exists()
    assert not storage_path.with_name(
        storage_path.name + ".tmp"
    ).exists()

    restored = ControlMissionDeliveryLeaseRegistry()
    assert persistence.restore(
        restored
    ) == 2
    assert restored.list() == [
        first,
        second,
    ]


def test_persistence_overwrites_released_lease_state(
    tmp_path: Path,
) -> None:
    persistence = ControlMissionDeliveryLeasePersistence(
        tmp_path / "control_leases.json"
    )
    registry = ControlMissionDeliveryLeaseRegistry()
    registry.acquire(
        build_lease()
    )
    persistence.save(
        registry
    )
    registry.release(
        "control-001"
    )

    persistence.save(
        registry
    )

    restored = ControlMissionDeliveryLeaseRegistry()
    assert persistence.restore(
        restored
    ) == 0
    assert restored.size() == 0


def test_restore_missing_file_returns_zero(
    tmp_path: Path,
) -> None:
    persistence = ControlMissionDeliveryLeasePersistence(
        tmp_path / "missing.json"
    )

    assert persistence.restore(
        ControlMissionDeliveryLeaseRegistry()
    ) == 0


def test_restore_rejects_non_list_payload(
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / "control_leases.json"
    storage_path.write_text(
        json.dumps(
            {"mission_id": "control-001"}
        ),
        encoding="utf-8",
    )
    persistence = ControlMissionDeliveryLeasePersistence(
        storage_path
    )

    with pytest.raises(
        ValueError,
        match="payload must be a list",
    ):
        persistence.restore(
            ControlMissionDeliveryLeaseRegistry()
        )


@pytest.mark.parametrize(
    "operation",
    [
        "save",
        "restore",
    ],
)
def test_persistence_rejects_invalid_registry(
    tmp_path: Path,
    operation: str,
) -> None:
    persistence = ControlMissionDeliveryLeasePersistence(
        tmp_path / "control_leases.json"
    )

    with pytest.raises(
        TypeError,
        match=(
            f"{operation} requires "
            "ControlMissionDeliveryLeaseRegistry"
        ),
    ):
        getattr(
            persistence,
            operation,
        )(
            "not-a-registry"
        )