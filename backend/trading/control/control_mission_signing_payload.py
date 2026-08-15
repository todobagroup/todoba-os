"""
TODOBA Control Mission Signing Payload

Builds the deterministic cross-language payload used for
control mission integrity signing.

Responsibilities:

- define the control signing domain and field order
- normalize control mission field values
- encode fields using length-prefixed framing
- produce deterministic UTF-8 signing bytes

This component does not create or verify HMAC signatures.
"""

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)


class ControlMissionSigningPayload:
    """
    Build the canonical signing payload shared by TODOBA
    Cloud and Trusted Execution Agents.
    """

    DOMAIN = "TODOBA_CONTROL_MISSION_V1"

    @classmethod
    def build(
        cls,
        mission: ControlMission,
    ) -> bytes:
        if not isinstance(
            mission,
            ControlMission,
        ):
            raise TypeError(
                "build requires ControlMission."
            )

        if not isinstance(
            mission.action,
            ControlAction,
        ):
            raise TypeError(
                "mission action must be ControlAction."
            )

        fields = (
            cls.DOMAIN,
            cls._string_value(
                mission.mission_id
            ),
            cls._string_value(
                mission.agent_id
            ),
            cls._string_value(
                mission.account_fingerprint
            ),
            mission.action.value,
            cls._string_value(
                mission.symbol
            ),
            str(
                mission.magic_number
            ),
            str(
                mission.requested_by_sender_id
            ),
            cls._string_value(
                mission.created_at
            ),
            cls._string_value(
                mission.expires_at
            ),
            str(
                mission.sequence
            ),
        )

        framed = "".join(
            cls._frame(
                value
            )
            for value in fields
        )

        return framed.encode(
            "utf-8"
        )

    @staticmethod
    def _frame(
        value: str,
    ) -> str:
        encoded = value.encode(
            "utf-8"
        )

        return (
            f"{len(encoded)}:"
            f"{value}"
        )

    @staticmethod
    def _string_value(
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "string signing field must be str."
            )

        return value