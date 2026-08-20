"""
TODOBA Telegram Dispatch Recovery

Restores durable pending Telegram dispatches after
Telegram executor restart.

Responsibilities:
- inspect durable per-target dispatch progress
- skip SUBMITTED dispatches
- skip EXPIRED dispatches
- expire stale PENDING missions without sending
- validate persisted mission ownership against the
  current Execution Target Registry
- resend only the exact persisted PENDING mission
- mark successful recovery dispatches SUBMITTED

This component does not:
- read Broker State
- parse Telegram messages
- make trading decisions
- calculate position size
- rebuild ExecutionMission payloads
- extend mission expiration
"""

from collections.abc import Callable
from datetime import UTC
from datetime import datetime

from backend.integrations.telegram_dispatch_progress_store import (
    TelegramDispatchProgressStore,
    TelegramDispatchStatus,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTargetRegistry,
)


class TelegramDispatchRecovery:
    """
    Startup recovery for durable Telegram dispatches.
    """

    def __init__(
        self,
        *,
        progress_store: TelegramDispatchProgressStore,
        execution_target_registry: ExecutionTargetRegistry,
        http_client,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(
            progress_store,
            TelegramDispatchProgressStore,
        ):
            raise TypeError(
                "TelegramDispatchRecovery requires "
                "TelegramDispatchProgressStore."
            )

        if not isinstance(
            execution_target_registry,
            ExecutionTargetRegistry,
        ):
            raise TypeError(
                "TelegramDispatchRecovery requires "
                "ExecutionTargetRegistry."
            )

        if not hasattr(
            http_client,
            "send",
        ):
            raise TypeError(
                "TelegramDispatchRecovery requires "
                "an HTTP client with send()."
            )

        if (
            clock is not None
            and not callable(
                clock
            )
        ):
            raise TypeError(
                "clock must be callable."
            )

        self.progress_store = progress_store
        self.execution_target_registry = (
            execution_target_registry
        )
        self.http_client = http_client
        self.clock = (
            clock
            if clock is not None
            else lambda: datetime.now(
                UTC
            )
        )

    @staticmethod
    def _parse_utc_datetime(
        value: str,
        *,
        field_name: str,
    ) -> datetime:
        if not isinstance(
            value,
            str,
        ):
            raise RuntimeError(
                f"{field_name} is invalid."
            )

        normalized = value.strip()

        if not normalized:
            raise RuntimeError(
                f"{field_name} is invalid."
            )

        if normalized.endswith(
            "Z"
        ):
            normalized = (
                normalized[:-1]
                + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                normalized
            )
        except ValueError as error:
            raise RuntimeError(
                f"{field_name} is invalid."
            ) from error

        if parsed.tzinfo is None:
            raise RuntimeError(
                f"{field_name} is invalid."
            )

        return parsed.astimezone(
            UTC
        )

    def _mission_is_expired(
        self,
        mission,
    ) -> bool:
        expires_at = (
            self._parse_utc_datetime(
                mission.expires_at,
                field_name=(
                    "Persisted Telegram dispatch "
                    "mission expires_at"
                ),
            )
        )

        current_time = self.clock()

        if not isinstance(
            current_time,
            datetime,
        ):
            raise RuntimeError(
                "Telegram dispatch recovery clock "
                "must return datetime."
            )

        if current_time.tzinfo is None:
            raise RuntimeError(
                "Telegram dispatch recovery clock "
                "must return timezone-aware datetime."
            )

        return (
            current_time.astimezone(
                UTC
            )
            >= expires_at
        )

    def _mission_matches_current_target(
        self,
        mission,
    ) -> bool:
        target = (
            self.execution_target_registry.get(
                agent_id=mission.agent_id
            )
        )

        if target is None:
            return False

        return (
            target.account_fingerprint
            == mission.account_fingerprint
        )

    def restore(
        self,
    ) -> int:
        """
        Recover eligible durable PENDING dispatches.

        Returns the number of missions successfully
        resent and marked SUBMITTED.
        """

        recovered_count = 0

        for progress in (
            self.progress_store.all()
        ):
            if (
                progress.status
                == TelegramDispatchStatus.SUBMITTED
            ):
                continue

            if (
                progress.status
                == TelegramDispatchStatus.EXPIRED
            ):
                continue

            if (
                progress.status
                != TelegramDispatchStatus.PENDING
            ):
                raise RuntimeError(
                    "Unknown Telegram dispatch status."
                )

            mission = progress.mission

            if self._mission_is_expired(
                mission
            ):
                self.progress_store.mark_expired(
                    chat_id=progress.chat_id,
                    message_id=progress.message_id,
                    agent_id=progress.agent_id,
                )

                continue

            if not self._mission_matches_current_target(
                mission
            ):
                continue

            self.http_client.send(
                mission
            )

            self.progress_store.mark_submitted(
                chat_id=progress.chat_id,
                message_id=progress.message_id,
                agent_id=progress.agent_id,
            )

            recovered_count += 1

        return recovered_count