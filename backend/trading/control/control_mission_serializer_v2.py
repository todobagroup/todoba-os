"""
TODOBA Control Mission Serializer V2

Owns serialization and deserialization of the
ControlMission V2 network contract.

V2 adds the Cloud-owned security sequence used for
replay protection.

The legacy V1 serializer remains unchanged.
"""

from typing import Any

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)


class ControlMissionSerializerV2:
    """
    Convert ControlMission V2 objects to and from
    JSON-safe payloads.
    """

    @staticmethod
    def serialize(
        mission: ControlMission,
    ) -> dict[str, Any]:
        if not isinstance(
            mission,
            ControlMission,
        ):
            raise TypeError(
                "serialize requires ControlMission."
            )

        if not isinstance(
            mission.action,
            ControlAction,
        ):
            raise TypeError(
                "mission action must be ControlAction."
            )

        ControlMissionSerializerV2._validate_security_sequence(
            mission.security_sequence
        )

        return {
            "mission_id": mission.mission_id,
            "agent_id": mission.agent_id,
            "account_fingerprint": (
                mission.account_fingerprint
            ),
            "action": mission.action.value,
            "symbol": mission.symbol,
            "magic_number": mission.magic_number,
            "requested_by_sender_id": (
                mission.requested_by_sender_id
            ),
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
    ) -> ControlMission:
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

        ControlMissionSerializerV2._validate_security_sequence(
            security_sequence
        )

        return ControlMission(
            mission_id=payload["mission_id"],
            agent_id=payload["agent_id"],
            account_fingerprint=payload[
                "account_fingerprint"
            ],
            action=ControlAction(
                payload["action"]
            ),
            symbol=payload["symbol"],
            magic_number=payload["magic_number"],
            requested_by_sender_id=payload[
                "requested_by_sender_id"
            ],
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