"""
TODOBA Control Mission Record Recovery

Restores persisted control mission records
back into the runtime registry.

Responsibilities:

- restore ControlMissionRegistry
- report restored record count

This component does not:

- execute control missions
- deliver control missions
- own persistence
- communicate with Trusted Agents
"""

from backend.trading.control.control_mission_record_persistence import (
    ControlMissionRecordPersistence,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)


class ControlMissionRecordRecovery:
    """
    Restore control mission lifecycle records
    from persistent storage.
    """

    def __init__(
        self,
        *,
        persistence: ControlMissionRecordPersistence,
        registry: ControlMissionRegistry,
    ) -> None:
        if not isinstance(
            persistence,
            ControlMissionRecordPersistence,
        ):
            raise TypeError(
                "ControlMissionRecordRecovery requires "
                "ControlMissionRecordPersistence."
            )

        if not isinstance(
            registry,
            ControlMissionRegistry,
        ):
            raise TypeError(
                "ControlMissionRecordRecovery requires "
                "ControlMissionRegistry."
            )

        self.persistence = persistence
        self.registry = registry

    def restore(
        self,
    ) -> int:
        """
        Restore all persisted control mission records.
        """

        return self.persistence.restore(
            self.registry
        )