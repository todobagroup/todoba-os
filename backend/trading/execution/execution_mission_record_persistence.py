"""
TODOBA Execution Mission Record Persistence

Persists execution mission lifecycle records to disk.

This component:
- saves ExecutionMissionRegistry
- restores ExecutionMissionRegistry
- preserves mission lifecycle state

It does not:
- execute broker orders
- receive HTTP requests
- own runtime lifecycle
"""

import json
from pathlib import Path

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


class ExecutionMissionRecordPersistence:
    """
    Persist ExecutionMissionRegistry lifecycle records
    to JSON.
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
        registry: ExecutionMissionRegistry,
    ) -> None:
        if not isinstance(
            registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "save requires ExecutionMissionRegistry."
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = []

        for record in registry.list():
            mission = record.mission

            payload.append(
                {
                    "mission": {
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
                    },
                    "status": record.status.value,
                    "delivered_at": record.delivered_at,
                    "acknowledged_at": (
                        record.acknowledged_at
                    ),
                    "started_at": record.started_at,
                    "completed_at": record.completed_at,
                    "failed_at": record.failed_at,
                    "failure_reason": (
                        record.failure_reason
                    ),
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
        registry: ExecutionMissionRegistry,
    ) -> int:
        if not isinstance(
            registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "restore requires ExecutionMissionRegistry."
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
            mission_payload = item["mission"]

            mission = ExecutionMission(
                mission_id=mission_payload[
                    "mission_id"
                ],
                agent_id=mission_payload["agent_id"],
                account_fingerprint=mission_payload[
                    "account_fingerprint"
                ],
                symbol=mission_payload["symbol"],
                order_type=mission_payload[
                    "order_type"
                ],
                volume=mission_payload["volume"],
                entry=mission_payload["entry"],
                sl=mission_payload["sl"],
                tp=mission_payload["tp"],
                magic_number=mission_payload[
                    "magic_number"
                ],
                comment=mission_payload["comment"],
                created_at=mission_payload[
                    "created_at"
                ],
                expires_at=mission_payload[
                    "expires_at"
                ],
                sequence=mission_payload["sequence"],
            )

            record = ExecutionMissionRecord(
                mission=mission,
                status=ExecutionMissionStatus(
                    item["status"]
                ),
                delivered_at=item["delivered_at"],
                acknowledged_at=item[
                    "acknowledged_at"
                ],
                started_at=item["started_at"],
                completed_at=item["completed_at"],
                failed_at=item["failed_at"],
                failure_reason=item[
                    "failure_reason"
                ],
            )

            registry.register(
                record
            )

            count += 1

        return count