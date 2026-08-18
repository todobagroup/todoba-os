"""
TODOBA Execution Mission Serializer V2

Owns serialization and deserialization of the
ExecutionMission V2 network contract.

V2 adds the Cloud-owned security sequence used for
replay protection.

The legacy V1 serializer remains unchanged.
"""

from typing import Any

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)


class ExecutionMissionSerializerV2:
    """
    Convert ExecutionMission V2 objects to and from
    JSON-safe payloads.
    """

    @staticmethod
    def serialize(
        mission: ExecutionMission,
    ) -> dict[str, Any]:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "serialize requires ExecutionMission."
            )

        ExecutionMissionSerializerV2._validate_security_sequence(
            mission.security_sequence
        )

        return {
            "mission_id": mission.mission_id,
            "agent_id": mission.agent_id,
            "account_fingerprint": (
                mission.account_fingerprint
            ),
            "symbol": mission.symbol,
            "order_type": mission.order_type,
            "volume": mission.volume,
            "entry": mission.entry,
            "sl": mission.sl,
            "tp": mission.tp,
            "magic_number": mission.magic_number,
            "comment": mission.comment,
            "created_at": mission.created_at,
            "expires_at": mission.expires_at,
            "sequence": mission.sequence,
            "security_sequence": (
                mission.security_sequence
            ),
        }

    @staticmethod
    def deserialize(
        payload: dict[str, Any],
    ) -> ExecutionMission:
        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "deserialize requires dict."
            )

        security_sequence = payload[
            "security_sequence"
        ]

        ExecutionMissionSerializerV2._validate_security_sequence(
            security_sequence
        )

        return ExecutionMission(
            mission_id=payload["mission_id"],
            agent_id=payload["agent_id"],
            account_fingerprint=payload[
                "account_fingerprint"
            ],
            symbol=payload["symbol"],
            order_type=payload["order_type"],
            volume=payload["volume"],
            entry=payload["entry"],
            sl=payload["sl"],
            tp=payload["tp"],
            magic_number=payload[
                "magic_number"
            ],
            comment=payload["comment"],
            created_at=payload["created_at"],
            expires_at=payload["expires_at"],
            sequence=payload["sequence"],
            security_sequence=security_sequence,
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