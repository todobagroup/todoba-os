"""
TODOBA Execution Mission Persistence

Persists execution missions to disk.

This component:
- saves ExecutionMissionRepository
- restores ExecutionMissionRepository

It does not:
- execute broker orders
- manage MT5
- own runtime lifecycle
"""

import json
from pathlib import Path

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)

from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)


class ExecutionMissionPersistence:
    """
    Persist ExecutionMissionRepository to JSON.
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
        repository: ExecutionMissionRepository,
    ) -> None:

        if not isinstance(
            repository,
            ExecutionMissionRepository,
        ):
            raise TypeError(
                "save requires "
                "ExecutionMissionRepository."
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = []

        for mission in repository.all():

            payload.append(
                {
                    "mission_id": mission.mission_id,
                    "agent_id": mission.agent_id,
                    "account_fingerprint": (
                        mission.account_fingerprint
                    ),
                    "symbol": mission.symbol,
                    "order_type": mission.order_type,
                    "volume": mission.volume,
                    "entry": mission.entry,
                    "sl": mission.sl,
                    "tp": mission.tp,
                    "magic_number": (
                        mission.magic_number
                    ),
                    "comment": mission.comment,
                    "created_at": mission.created_at,
                    "expires_at": mission.expires_at,
                    "sequence": mission.sequence,
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
        repository: ExecutionMissionRepository,
    ) -> int:

        if not isinstance(
            repository,
            ExecutionMissionRepository,
        ):
            raise TypeError(
                "restore requires "
                "ExecutionMissionRepository."
            )

        if not self.storage_path.exists():
            return 0

        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8",
            )
        )

        count = 0

        for item in payload:

            repository.save(
                ExecutionMission(
                    mission_id=item["mission_id"],
                    agent_id=item["agent_id"],
                    account_fingerprint=(
                        item["account_fingerprint"]
                    ),
                    symbol=item["symbol"],
                    order_type=item["order_type"],
                    volume=item["volume"],
                    entry=item["entry"],
                    sl=item["sl"],
                    tp=item["tp"],
                    magic_number=(
                        item["magic_number"]
                    ),
                    comment=item["comment"],
                    created_at=item["created_at"],
                    expires_at=item["expires_at"],
                    sequence=item["sequence"],
                )
            )

            count += 1

        return count