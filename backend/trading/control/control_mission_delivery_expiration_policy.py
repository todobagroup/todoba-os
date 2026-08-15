"""
TODOBA Control Mission Delivery Expiration Policy

Determines whether a control mission is still eligible
for delivery based on its expiration time.

Responsibilities:
- evaluate control mission expiration
- compare mission expiration against current time
- provide a delivery eligibility decision

This component does not:
- remove missions from delivery storage
- create delivery leases
- modify mission lifecycle
- receive HTTP requests
- control broker trades
"""

from datetime import datetime
from datetime import timezone

from backend.trading.control.control_mission import (
    ControlMission,
)


class ControlMissionDeliveryExpirationPolicy:
    """
    Determine whether a control mission has expired
    before delivery.
    """

    def is_expired(
        self,
        mission: ControlMission,
        current_time: datetime,
    ) -> bool:
        if not isinstance(
            mission,
            ControlMission,
        ):
            raise TypeError(
                "is_expired requires ControlMission."
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

        expires_at = self._parse_timestamp(
            mission.expires_at
        )

        return normalized_current_time >= expires_at

    def is_eligible(
        self,
        mission: ControlMission,
        current_time: datetime,
    ) -> bool:
        return not self.is_expired(
            mission,
            current_time,
        )

    def _parse_timestamp(
        self,
        value: str,
    ) -> datetime:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "expires_at must be str."
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
                "expires_at must use ISO 8601 format."
            ) from error

        return self._normalize_datetime(
            parsed
        )

    @staticmethod
    def _normalize_datetime(
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )