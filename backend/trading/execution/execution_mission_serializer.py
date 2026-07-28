"""
TODOBA Execution Mission Serializer

Owns serialization and deserialization of the
ExecutionMission network contract.

Transport and security belong to separate capabilities.
"""

from dataclasses import asdict
from typing import Any

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)


class ExecutionMissionSerializer:
    """
    Convert ExecutionMission objects to and from
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

        return asdict(
            mission
        )

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
            magic_number=payload["magic_number"],
            comment=payload["comment"],
            created_at=payload["created_at"],
            expires_at=payload["expires_at"],
            sequence=payload["sequence"],
        )