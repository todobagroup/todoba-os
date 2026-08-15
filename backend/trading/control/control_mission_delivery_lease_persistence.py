"""
TODOBA Control Mission Delivery Lease Persistence

Persists active control mission delivery leases to disk.

Responsibilities:
- atomically save active delivery leases
- restore active delivery leases

This component does not:
- create leases
- deliver control missions
- acknowledge control missions
- retry missions
- own runtime lifecycle
"""

import json
from pathlib import Path

from backend.trading.control.control_mission_delivery_lease import (
    ControlMissionDeliveryLease,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)


class ControlMissionDeliveryLeasePersistence:
    """
    Persist active control mission delivery leases to JSON.
    """

    def __init__(
        self,
        storage_path: Path,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        self.storage_path = storage_path

    def save(
        self,
        registry: ControlMissionDeliveryLeaseRegistry,
    ) -> None:
        if not isinstance(
            registry,
            ControlMissionDeliveryLeaseRegistry,
        ):
            raise TypeError(
                "save requires "
                "ControlMissionDeliveryLeaseRegistry."
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = [
            {
                "mission_id": lease.mission_id,
                "agent_id": lease.agent_id,
                "leased_at": lease.leased_at,
                "expires_at": lease.expires_at,
            }
            for lease in registry.list()
        ]

        temporary_path = self.storage_path.with_name(
            self.storage_path.name + ".tmp"
        )

        try:
            temporary_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            temporary_path.replace(
                self.storage_path
            )
        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()
            raise

    def restore(
        self,
        registry: ControlMissionDeliveryLeaseRegistry,
    ) -> int:
        if not isinstance(
            registry,
            ControlMissionDeliveryLeaseRegistry,
        ):
            raise TypeError(
                "restore requires "
                "ControlMissionDeliveryLeaseRegistry."
            )

        if not self.storage_path.exists():
            return 0

        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8",
            )
        )

        if not isinstance(
            payload,
            list,
        ):
            raise ValueError(
                "Control delivery lease persistence "
                "payload must be a list."
            )

        count = 0

        for item in payload:
            registry.acquire(
                ControlMissionDeliveryLease(
                    mission_id=item["mission_id"],
                    agent_id=item["agent_id"],
                    leased_at=item["leased_at"],
                    expires_at=item["expires_at"],
                )
            )

            count += 1

        return count