"""
TODOBA Execution Mission Registry

Owns active ExecutionMissionRecord objects.

This component tracks organizational mission records.

It does not:
- execute missions
- communicate with agents
- manage broker execution
"""

from typing import Optional

from backend.trading.execution.execution_mission_record import (
    ExecutionMissionRecord,
)


class ExecutionMissionRegistry:
    """
    Registry for active execution mission records.
    """

    def __init__(self) -> None:
        self._records: dict[str, ExecutionMissionRecord] = {}

    def register(
        self,
        record: ExecutionMissionRecord,
    ) -> ExecutionMissionRecord:

        if not isinstance(
            record,
            ExecutionMissionRecord,
        ):
            raise TypeError(
                "register requires ExecutionMissionRecord."
            )

        mission_id = record.mission.mission_id

        self._records[mission_id] = record

        return record

    def get(
        self,
        mission_id: str,
    ) -> Optional[ExecutionMissionRecord]:

        return self._records.get(
            mission_id
        )

    def list(
        self,
    ) -> list[ExecutionMissionRecord]:

        return list(
            self._records.values()
        )

    def size(
        self,
    ) -> int:

        return len(
            self._records
        )