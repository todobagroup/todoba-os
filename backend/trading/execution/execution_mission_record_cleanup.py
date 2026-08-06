"""
TODOBA Execution Mission Record Cleanup

Removes execution mission records from the registry
according to an external retention decision.

Responsibilities:
- remove records from ExecutionMissionRegistry
- persist registry after cleanup

This component does not:
- decide retention policy
- execute missions
- communicate with agents
- modify broker evidence
"""

from typing import Iterable

from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


class ExecutionMissionRecordCleanup:
    """
    Cleans execution mission records from the registry.
    """

    def __init__(
        self,
        registry: ExecutionMissionRegistry,
        persistence: ExecutionMissionRecordPersistence,
    ) -> None:

        if not isinstance(
            registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "ExecutionMissionRecordCleanup "
                "requires ExecutionMissionRegistry."
            )

        if not isinstance(
            persistence,
            ExecutionMissionRecordPersistence,
        ):
            raise TypeError(
                "ExecutionMissionRecordCleanup "
                "requires "
                "ExecutionMissionRecordPersistence."
            )

        self.registry = registry
        self.persistence = persistence

    def cleanup(
        self,
        mission_ids: Iterable[str],
    ) -> int:
        """
        Remove the supplied mission IDs from the registry.

        Returns
        -------
        int
            Number of removed records.
        """

        removed = 0

        for mission_id in mission_ids:
            if self.registry.remove(
                mission_id
            ):
                removed += 1

        if removed > 0:
            self.persistence.save(
                self.registry
            )

        return removed