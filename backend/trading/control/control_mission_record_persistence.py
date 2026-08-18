"""
TODOBA Control Mission Record Persistence

Persists control mission lifecycle records to disk.

This component preserves lifecycle state, delivery
attempts, and broker control result counts. It does not
deliver missions or control broker trades.
"""

import json
from dataclasses import replace
from pathlib import Path

from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_serializer import (
    ControlMissionSerializer,
)
from backend.trading.control.control_mission_status import (
    ControlMissionStatus,
)


class ControlMissionRecordPersistence:
    """
    Persist ControlMissionRegistry lifecycle records to
    JSON.
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
        registry: ControlMissionRegistry,
    ) -> None:
        if not isinstance(
            registry,
            ControlMissionRegistry,
        ):
            raise TypeError(
                "save requires ControlMissionRegistry."
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = []

        for record in registry.list():
            mission_payload = (
                ControlMissionSerializer.serialize(
                    record.mission
                )
            )

            mission_payload[
                "security_sequence"
            ] = record.mission.security_sequence

            payload.append(
                {
                    "mission": mission_payload,
                    "status": record.status.value,
                    "delivered_at": record.delivered_at,
                    "delivery_attempt_count": (
                        record.delivery_attempt_count
                    ),
                    "acknowledged_at": (
                        record.acknowledged_at
                    ),
                    "started_at": record.started_at,
                    "completed_at": record.completed_at,
                    "failed_at": record.failed_at,
                    "failure_reason": (
                        record.failure_reason
                    ),
                    "matched_position_count": (
                        record.matched_position_count
                    ),
                    "closed_position_count": (
                        record.closed_position_count
                    ),
                    "matched_pending_order_count": (
                        record.matched_pending_order_count
                    ),
                    "canceled_pending_order_count": (
                        record.canceled_pending_order_count
                    ),
                    "failed_item_count": (
                        record.failed_item_count
                    ),
                }
            )

        temporary_path = self.storage_path.with_suffix(
            self.storage_path.suffix + ".tmp"
        )

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

    def restore(
        self,
        registry: ControlMissionRegistry,
    ) -> int:
        if not isinstance(
            registry,
            ControlMissionRegistry,
        ):
            raise TypeError(
                "restore requires "
                "ControlMissionRegistry."
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

            mission = (
                ControlMissionSerializer.deserialize(
                    mission_payload
                )
            )

            mission = replace(
                mission,
                security_sequence=mission_payload.get(
                    "security_sequence",
                    0,
                ),
            )

            record = ControlMissionRecord(
                mission=mission,
                status=ControlMissionStatus(
                    item["status"]
                ),
                delivered_at=item["delivered_at"],
                delivery_attempt_count=item.get(
                    "delivery_attempt_count",
                    0,
                ),
                acknowledged_at=item[
                    "acknowledged_at"
                ],
                started_at=item["started_at"],
                completed_at=item["completed_at"],
                failed_at=item["failed_at"],
                failure_reason=item[
                    "failure_reason"
                ],
                matched_position_count=item.get(
                    "matched_position_count",
                    0,
                ),
                closed_position_count=item.get(
                    "closed_position_count",
                    0,
                ),
                matched_pending_order_count=item.get(
                    "matched_pending_order_count",
                    0,
                ),
                canceled_pending_order_count=item.get(
                    "canceled_pending_order_count",
                    0,
                ),
                failed_item_count=item.get(
                    "failed_item_count",
                    0,
                ),
            )

            registry.register(
                record
            )

            count += 1

        return count