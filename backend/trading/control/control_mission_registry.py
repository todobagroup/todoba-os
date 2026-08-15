"""
TODOBA Control Mission Registry

Owns active ControlMissionRecord objects.

This component tracks organizational control records. It
does not deliver missions or control broker trades.
"""

from typing import Optional

from backend.trading.control.control_mission_record import (
    ControlMissionRecord,
)


class ControlMissionRegistry:
    """
    Registry for active control mission records.
    """

    def __init__(self) -> None:
        self._records: dict[
            str,
            ControlMissionRecord,
        ] = {}

    def register(
        self,
        record: ControlMissionRecord,
    ) -> ControlMissionRecord:
        if not isinstance(
            record,
            ControlMissionRecord,
        ):
            raise TypeError(
                "register requires "
                "ControlMissionRecord."
            )

        mission_id = record.mission.mission_id

        existing = self._records.get(
            mission_id
        )

        if existing is not None:
            if existing.mission != record.mission:
                raise ValueError(
                    "mission_id already exists with "
                    "different payload."
                )

            return existing

        self._records[
            mission_id
        ] = record

        return record

    def get(
        self,
        mission_id: str,
    ) -> Optional[ControlMissionRecord]:
        return self._records.get(
            mission_id
        )

    def remove(
        self,
        mission_id: str,
    ) -> bool:
        if mission_id not in self._records:
            return False

        del self._records[
            mission_id
        ]

        return True

    def list(self) -> list[ControlMissionRecord]:
        return list(
            self._records.values()
        )

    def size(self) -> int:
        return len(
            self._records
        )