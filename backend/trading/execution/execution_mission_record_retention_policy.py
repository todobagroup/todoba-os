"""
TODOBA Execution Mission Record Retention Policy

Selects terminal execution mission records
that have exceeded the configured retention period.

Responsibilities:
- evaluate terminal mission records
- return removable mission IDs

This component does not:
- remove records
- persist registry changes
- read system time
- execute missions
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_status import (
    ExecutionMissionStatus,
)


class ExecutionMissionRecordRetentionPolicy:
    """
    Select execution mission records eligible
    for cleanup.
    """

    def __init__(
        self,
        retention_days: int,
    ) -> None:
        if not isinstance(
            retention_days,
            int,
        ):
            raise TypeError(
                "retention_days must be int."
            )

        if retention_days < 0:
            raise ValueError(
                "retention_days must not be negative."
            )

        self.retention_days = retention_days

    def select(
        self,
        registry: ExecutionMissionRegistry,
        current_time: datetime,
    ) -> list[str]:
        if not isinstance(
            registry,
            ExecutionMissionRegistry,
        ):
            raise TypeError(
                "select requires ExecutionMissionRegistry."
            )

        if not isinstance(
            current_time,
            datetime,
        ):
            raise TypeError(
                "current_time must be datetime."
            )

        normalized_current_time = (
            self._normalize_datetime(
                current_time
            )
        )

        retention_threshold = (
            normalized_current_time
            - timedelta(
                days=self.retention_days
            )
        )

        mission_ids = []

        for record in registry.list():
            terminal_time = (
                self._terminal_time(
                    record.status,
                    record.completed_at,
                    record.failed_at,
                )
            )

            if terminal_time is None:
                continue

            if terminal_time <= retention_threshold:
                mission_ids.append(
                    record.mission.mission_id
                )

        return mission_ids

    def _terminal_time(
        self,
        status: ExecutionMissionStatus,
        completed_at: str | None,
        failed_at: str | None,
    ) -> datetime | None:
        if (
            status
            == ExecutionMissionStatus.COMPLETED
        ):
            if completed_at is None:
                return None

            return self._parse_timestamp(
                completed_at
            )

        if (
            status
            == ExecutionMissionStatus.FAILED
        ):
            if failed_at is None:
                return None

            return self._parse_timestamp(
                failed_at
            )

        return None

    def _parse_timestamp(
        self,
        value: str,
    ) -> datetime:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "timestamp must be str."
            )

        normalized_value = value

        if normalized_value.endswith(
            "Z"
        ):
            normalized_value = (
                normalized_value[:-1]
                + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                normalized_value
            )
        except ValueError as error:
            raise ValueError(
                "timestamp must use ISO 8601 format."
            ) from error

        return self._normalize_datetime(
            parsed
        )

    def _normalize_datetime(
        self,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )