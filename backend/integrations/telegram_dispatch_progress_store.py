"""
TODOBA Telegram Dispatch Progress Store

Owns durable per-target Telegram dispatch progress.

Responsibilities:
- preserve the exact ExecutionMission before HTTP dispatch
- track per-source, per-target dispatch status
- provide idempotent preparation
- reject conflicting mission payloads
- atomically persist dispatch progress
- restore dispatch progress after restart

This component does not:
- read Broker State
- make trading decisions
- size positions
- submit HTTP requests
- own Cloud mission lifecycle
"""

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)


class TelegramDispatchStatus(str, Enum):
    """
    Durable Telegram dispatch state.
    """

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class TelegramDispatchProgress:
    """
    Immutable per-target Telegram dispatch progress.
    """

    chat_id: int
    message_id: int
    agent_id: str
    mission: ExecutionMission
    status: TelegramDispatchStatus


class TelegramDispatchProgressStore:
    """
    Durable store for per-target Telegram dispatch progress.

    Identity:

    (chat_id, message_id, agent_id)
    """

    def __init__(
        self,
        *,
        storage_path: Path,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        self.storage_path = storage_path

        self._progress: dict[
            tuple[int, int, str],
            TelegramDispatchProgress,
        ] = {}

        self._restore()

    @staticmethod
    def _key(
        *,
        chat_id: int,
        message_id: int,
        agent_id: str,
    ) -> tuple[int, int, str]:
        if not isinstance(
            chat_id,
            int,
        ):
            raise TypeError(
                "chat_id must be int."
            )

        if not isinstance(
            message_id,
            int,
        ):
            raise TypeError(
                "message_id must be int."
            )

        if not isinstance(
            agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be str."
            )

        normalized_agent_id = (
            agent_id.strip()
        )

        if not normalized_agent_id:
            raise ValueError(
                "agent_id is required."
            )

        return (
            chat_id,
            message_id,
            normalized_agent_id,
        )

    @staticmethod
    def _serialize_mission(
        mission: ExecutionMission,
    ) -> dict:
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
            "magic_number": (
                mission.magic_number
            ),
            "comment": mission.comment,
            "created_at": mission.created_at,
            "expires_at": mission.expires_at,
            "sequence": mission.sequence,
            "security_sequence": (
                mission.security_sequence
            ),
        }

    @staticmethod
    def _deserialize_mission(
        payload: dict,
    ) -> ExecutionMission:
        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Telegram dispatch mission payload "
                "must be an object."
            )

        return ExecutionMission(
            mission_id=payload["mission_id"],
            agent_id=payload["agent_id"],
            account_fingerprint=(
                payload["account_fingerprint"]
            ),
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
            security_sequence=payload.get(
                "security_sequence",
                0,
            ),
        )

    def _save(
        self,
    ) -> None:
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = [
            {
                "chat_id": progress.chat_id,
                "message_id": (
                    progress.message_id
                ),
                "agent_id": progress.agent_id,
                "status": (
                    progress.status.value
                ),
                "mission": (
                    self._serialize_mission(
                        progress.mission
                    )
                ),
            }
            for progress
            in self._progress.values()
        ]

        temporary_path = (
            self.storage_path.with_name(
                self.storage_path.name
                + ".tmp"
            )
        )

        try:
            temporary_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            temporary_path.replace(
                self.storage_path
            )

        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()

            raise

    def _restore(
        self,
    ) -> int:
        if not self.storage_path.exists():
            return 0

        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8",
            )
        )

        if not isinstance(
            payload,
            list,
        ):
            raise ValueError(
                "Telegram dispatch progress "
                "payload must be a list."
            )

        restored: dict[
            tuple[int, int, str],
            TelegramDispatchProgress,
        ] = {}

        for item in payload:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Telegram dispatch progress "
                    "record must be an object."
                )

            mission = (
                self._deserialize_mission(
                    item["mission"]
                )
            )

            status = TelegramDispatchStatus(
                item["status"]
            )

            key = self._key(
                chat_id=item["chat_id"],
                message_id=item["message_id"],
                agent_id=item["agent_id"],
            )

            if key in restored:
                raise ValueError(
                    "Duplicate Telegram dispatch "
                    "progress record."
                )

            if (
                mission.agent_id
                != key[2]
            ):
                raise ValueError(
                    "Telegram dispatch progress "
                    "Agent does not match mission."
                )

            restored[key] = (
                TelegramDispatchProgress(
                    chat_id=key[0],
                    message_id=key[1],
                    agent_id=key[2],
                    mission=mission,
                    status=status,
                )
            )

        self._progress = restored

        return len(
            restored
        )

    def prepare(
        self,
        *,
        chat_id: int,
        message_id: int,
        mission: ExecutionMission,
    ) -> TelegramDispatchProgress:
        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "prepare requires ExecutionMission."
            )

        key = self._key(
            chat_id=chat_id,
            message_id=message_id,
            agent_id=mission.agent_id,
        )

        existing = self._progress.get(
            key
        )

        if existing is not None:
            if existing.mission != mission:
                raise ValueError(
                    "Telegram dispatch progress conflict."
                )

            return existing

        progress = TelegramDispatchProgress(
            chat_id=key[0],
            message_id=key[1],
            agent_id=key[2],
            mission=mission,
            status=(
                TelegramDispatchStatus.PENDING
            ),
        )

        self._progress[key] = progress

        try:
            self._save()
        except Exception:
            self._progress.pop(
                key,
                None,
            )
            raise

        return progress

    def get(
        self,
        *,
        chat_id: int,
        message_id: int,
        agent_id: str,
    ) -> TelegramDispatchProgress | None:
        key = self._key(
            chat_id=chat_id,
            message_id=message_id,
            agent_id=agent_id,
        )

        return self._progress.get(
            key
        )

    def mark_submitted(
        self,
        *,
        chat_id: int,
        message_id: int,
        agent_id: str,
    ) -> TelegramDispatchProgress:
        key = self._key(
            chat_id=chat_id,
            message_id=message_id,
            agent_id=agent_id,
        )

        existing = self._progress.get(
            key
        )

        if existing is None:
            raise KeyError(
                "Telegram dispatch progress "
                "was not found."
            )

        if (
            existing.status
            == TelegramDispatchStatus.SUBMITTED
        ):
            return existing

        submitted = TelegramDispatchProgress(
            chat_id=existing.chat_id,
            message_id=existing.message_id,
            agent_id=existing.agent_id,
            mission=existing.mission,
            status=(
                TelegramDispatchStatus.SUBMITTED
            ),
        )

        self._progress[key] = submitted

        try:
            self._save()
        except Exception:
            self._progress[key] = existing
            raise

        return submitted

    def mark_expired(
        self,
        *,
        chat_id: int,
        message_id: int,
        agent_id: str,
    ) -> TelegramDispatchProgress:
        key = self._key(
            chat_id=chat_id,
            message_id=message_id,
            agent_id=agent_id,
        )

        existing = self._progress.get(
            key
        )

        if existing is None:
            raise KeyError(
                "Telegram dispatch progress "
                "was not found."
            )

        if (
            existing.status
            == TelegramDispatchStatus.EXPIRED
        ):
            return existing

        if (
            existing.status
            == TelegramDispatchStatus.SUBMITTED
        ):
            raise ValueError(
                "Submitted Telegram dispatch progress "
                "cannot be marked expired."
            )

        expired = TelegramDispatchProgress(
            chat_id=existing.chat_id,
            message_id=existing.message_id,
            agent_id=existing.agent_id,
            mission=existing.mission,
            status=(
                TelegramDispatchStatus.EXPIRED
            ),
        )

        self._progress[key] = expired

        try:
            self._save()
        except Exception:
            self._progress[key] = existing
            raise

        return expired

    def all(
        self,
    ) -> tuple[
        TelegramDispatchProgress,
        ...,
    ]:
        return tuple(
            self._progress.values()
        )

    def size(
        self,
    ) -> int:
        return len(
            self._progress
        )