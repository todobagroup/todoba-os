"""
TODOBA Execution Mission Delivery Lease Persistence

Persists active execution mission delivery leases to disk.

Responsibilities:
- save active delivery leases
- restore active delivery leases

This component does not:
- create leases
- deliver missions
- acknowledge missions
- retry missions
- own runtime lifecycle
"""

import json
from pathlib import Path

from backend.trading.execution.execution_mission_delivery_lease import (
    ExecutionMissionDeliveryLease,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)


class ExecutionMissionDeliveryLeasePersistence:
    """
    Persist active delivery leases to JSON.
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
        registry: ExecutionMissionDeliveryLeaseRegistry,
    ) -> None:
        if not isinstance(
            registry,
            ExecutionMissionDeliveryLeaseRegistry,
        ):
            raise TypeError(
                "save requires "
                "ExecutionMissionDeliveryLeaseRegistry."
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = []

        for lease in registry.list():
            payload.append(
                {
                    "mission_id": lease.mission_id,
                    "agent_id": lease.agent_id,
                    "leased_at": lease.leased_at,
                    "expires_at": lease.expires_at,
                }
            )

        self.storage_path.write_text(
            json.dumps(
                payload,
                indent=2,
            ),
            encoding="utf-8",
        )

    def restore(
        self,
        registry: ExecutionMissionDeliveryLeaseRegistry,
    ) -> int:
        if not isinstance(
            registry,
            ExecutionMissionDeliveryLeaseRegistry,
        ):
            raise TypeError(
                "restore requires "
                "ExecutionMissionDeliveryLeaseRegistry."
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
                "Delivery lease persistence payload "
                "must be a list."
            )

        count = 0

        for item in payload:
            registry.acquire(
                ExecutionMissionDeliveryLease(
                    mission_id=item["mission_id"],
                    agent_id=item["agent_id"],
                    leased_at=item["leased_at"],
                    expires_at=item["expires_at"],
                )
            )

            count += 1

        return count