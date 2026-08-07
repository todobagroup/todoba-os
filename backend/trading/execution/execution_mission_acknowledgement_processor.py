"""
TODOBA Execution Mission Acknowledgement Processor

Consumes acknowledgement evidence and coordinates
mission lifecycle updates.

Responsibilities:
- process acknowledgement evidence
- remove successfully processed evidence
  from persistence

This component does not:
- receive HTTP requests
- store acknowledgement evidence
- execute broker orders
"""

from typing import Optional

from backend.trading.execution.execution_mission_acknowledgement import (
    ExecutionMissionAcknowledgement,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)


class ExecutionMissionAcknowledgementProcessor:
    """
    Processes Trusted Agent acknowledgement evidence.
    """

    def __init__(
        self,
        *,
        store: ExecutionMissionAcknowledgementStore,
        lifecycle_service: ExecutionMissionLifecycleService,
        persistence: Optional[
            ExecutionMissionEvidencePersistence
        ] = None,
    ) -> None:
        if not isinstance(
            store,
            ExecutionMissionAcknowledgementStore,
        ):
            raise TypeError(
                "ExecutionMissionAcknowledgementProcessor "
                "requires ExecutionMissionAcknowledgementStore."
            )

        if not isinstance(
            lifecycle_service,
            ExecutionMissionLifecycleService,
        ):
            raise TypeError(
                "ExecutionMissionAcknowledgementProcessor "
                "requires ExecutionMissionLifecycleService."
            )

        if (
            persistence is not None
            and not isinstance(
                persistence,
                ExecutionMissionEvidencePersistence,
            )
        ):
            raise TypeError(
                "persistence must be "
                "ExecutionMissionEvidencePersistence."
            )

        self.store = store
        self.lifecycle_service = lifecycle_service
        self.persistence = persistence

    def process_next(
        self,
    ):
        acknowledgement = self.store.pop()

        if acknowledgement is None:
            return None

        result = self.lifecycle_service.acknowledge(
            mission_id=acknowledgement.mission_id,
            acknowledged_at=(
                acknowledgement.acknowledged_at
            ),
        )

        if self.persistence is not None:
            self.persistence.remove(
                acknowledgement
            )

        return result