"""
TODOBA Control Mission Signing Payload V2

Builds the deterministic cross-language payload used
for ControlMission V2 integrity signing.

V2 introduces:

- the TODOBA_CONTROL_MISSION_V2 signing domain
- the Cloud-owned security_sequence field

The legacy V1 signing payload remains unchanged.
"""

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)


class ControlMissionSigningPayloadV2:
    """
    Build the canonical ControlMission V2 signing
    payload shared by TODOBA Cloud and Trusted Agents.
    """

    DOMAIN = "TODOBA_CONTROL_MISSION_V2"

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

        cls._validate_security_sequence(
            mission.security_sequence
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
            str(
                mission.security_sequence
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

    @staticmethod
    def _validate_security_sequence(
        security_sequence: int,
    ) -> None:
        if (
            not isinstance(
                security_sequence,
                int,
            )
            or isinstance(
                security_sequence,
                bool,
            )
            or security_sequence <= 0
        ):
            raise ValueError(
                "security_sequence must be "
                "a positive integer."
            )