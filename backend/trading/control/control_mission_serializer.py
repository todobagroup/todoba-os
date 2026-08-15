"""
TODOBA Control Mission Serializer

Owns serialization and deserialization of the
ControlMission network contract.

Transport, authentication, signing, lifecycle tracking,
and broker control belong to separate capabilities.
"""

from typing import Any

from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)


class ControlMissionSerializer:
    """
    Convert ControlMission objects to and from JSON-safe
    payloads.
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
        )