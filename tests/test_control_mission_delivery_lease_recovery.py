from pathlib import Path

import pytest

from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
)
from backend.trading.control.control_mission_delivery_lease_persistence import (
    ControlMissionDeliveryLeasePersistence,
)
from backend.trading.control.control_mission_delivery_lease_recovery import (
    ControlMissionDeliveryLeaseRecovery,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)


def build_lease() -> ControlMissionDeliveryLease:
    return ControlMissionDeliveryLease(
        mission_id="control-001",
        agent_id="trusted-agent-001",
        leased_at="2026-08-15T00:00:00Z",
        expires_at="2026-08-15T00:00:30Z",
    )


def test_recovery_restores_persisted_leases(
    tmp_path: Path,
) -> None:
    persistence = ControlMissionDeliveryLeasePersistence(
        tmp_path / "control_leases.json"
    )
    source = ControlMissionDeliveryLeaseRegistry()
    lease = build_lease()
    source.acquire(
        lease
    )
    persistence.save(
        source
    )
    restored = ControlMissionDeliveryLeaseRegistry()
    recovery = ControlMissionDeliveryLeaseRecovery(
        persistence=persistence,
        registry=restored,
    )

    count = recovery.restore()

    assert count == 1
    assert restored.get(
        "control-001"
    ) == lease


def test_recovery_returns_zero_when_file_is_missing(
    tmp_path: Path,
) -> None:
    recovery = ControlMissionDeliveryLeaseRecovery(
        persistence=(
            ControlMissionDeliveryLeasePersistence(
                tmp_path / "missing.json"
            )
        ),
        registry=ControlMissionDeliveryLeaseRegistry(),
    )

    assert recovery.restore() == 0


@pytest.mark.parametrize(
    "invalid_name",
    [
        "persistence",
        "registry",
    ],
)
def test_recovery_rejects_invalid_dependency(
    tmp_path: Path,
    invalid_name: str,
) -> None:
    dependencies = {
        "persistence": (
            ControlMissionDeliveryLeasePersistence(
                tmp_path / "control_leases.json"
            )
        ),
        "registry": ControlMissionDeliveryLeaseRegistry(),
    }
    dependencies[invalid_name] = "invalid"

    with pytest.raises(
        TypeError,
        match=(
            "ControlMissionDeliveryLeaseRecovery requires"
        ),
    ):
        ControlMissionDeliveryLeaseRecovery(
            **dependencies
        )