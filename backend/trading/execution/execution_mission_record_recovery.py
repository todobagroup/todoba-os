"""
TODOBA Execution Mission Record Recovery

Restores persisted execution mission records
back into the runtime registry.

Responsibilities:
- restore ExecutionMissionRegistry
- report restored record count

This component does not:
- execute missions
- deliver missions
- own persistence
- communicate with agents
"""

from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)


class ExecutionMissionRecordRecovery:
    """
    Restores execution mission records
    from persistent storage.
    """

    def __init__(
        self,
        persistence: ExecutionMissionRecordPersistence,
        registry: ExecutionMissionRegistry,
    ) -> None:

        if not isinstance(
            persistence,
            ExecutionMissionRecordPersistence,
        ):
            raise TypeError(
                "ExecutionMissionRecordRecovery "
                "requires "
                "ExecutionMissionRecordPersistence."
            )

        if not isinstance(
            registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "ExecutionMissionRecordRecovery "
                "requires "
                "ExecutionMissionRegistry."
            )

        self.persistence = persistence
        self.registry = registry

    def restore(
        self,
    ) -> int:
        """
        Restore all persisted mission records.

        Returns
        -------
        int
            Number of restored records.
        """

        return self.persistence.restore(
            self.registry
        )