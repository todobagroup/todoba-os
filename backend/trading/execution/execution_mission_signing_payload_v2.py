"""
TODOBA Execution Mission Signing Payload V2

Builds the deterministic cross-language payload used
for ExecutionMission V2 integrity signing.

V2 introduces:

- an explicit execution signing domain
- the Cloud-owned security_sequence field

The legacy V1 signing payload remains unchanged.
"""

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)


class ExecutionMissionSigningPayloadV2:
    """
    Build the canonical ExecutionMission V2 signing
    payload shared by TODOBA Cloud and Trusted Agents.
    """

    DOMAIN = "TODOBA_EXECUTION_MISSION_V2"

    @classmethod
    def build(
        cls,
        mission: ExecutionMission,
    ) -> bytes:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "build requires ExecutionMission."
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
            cls._string_value(
                mission.symbol
            ),
            cls._string_value(
                mission.order_type
            ),
            cls._float_value(
                mission.volume
            ),
            cls._optional_float_value(
                mission.entry
            ),
            cls._float_value(
                mission.sl
            ),
            cls._float_value(
                mission.tp
            ),
            str(
                mission.magic_number
            ),
            cls._string_value(
                mission.comment
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
    def _float_value(
        value: float,
    ) -> str:
        if not isinstance(
            value,
            (int, float),
        ):
            raise TypeError(
                "numeric signing field must be numeric."
            )

        normalized = format(
            float(value),
            ".8f",
        ).rstrip(
            "0"
        ).rstrip(
            "."
        )

        if normalized == "-0":
            return "0"

        return normalized

    @classmethod
    def _optional_float_value(
        cls,
        value: float | None,
    ) -> str:
        if value is None:
            return "null"

        return cls._float_value(
            value
        )

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