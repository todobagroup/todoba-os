"""
TODOBA Broker State Store

Stores the latest BrokerState observed for each
account, symbol, and authenticated Trusted Agent.

The Store also records when TODOBA Cloud received
the latest state from each Agent.
"""

from datetime import UTC
from datetime import datetime
from typing import Callable

from backend.trading.execution.broker_state import (
    BrokerState,
)


def _utc_now() -> datetime:
    return datetime.now(
        UTC
    )


class BrokerStateStore:
    """
    Store the latest broker state by account and agent.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self._clock = clock

        self._states: dict[
            tuple[str, str],
            BrokerState,
        ] = {}

        self._agent_states: dict[
            str,
            BrokerState,
        ] = {}

        self._agent_received_at: dict[
            str,
            datetime,
        ] = {}

    @staticmethod
    def _normalize_agent_id(
        agent_id: str,
    ) -> str:
        if not isinstance(
            agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be str."
            )

        normalized_agent_id = agent_id.strip()

        if not normalized_agent_id:
            raise ValueError(
                "agent_id is required."
            )

        return normalized_agent_id

    def save(
        self,
        state: BrokerState,
        *,
        agent_id: str | None = None,
    ) -> None:
        if not isinstance(
            state,
            BrokerState,
        ):
            raise TypeError(
                "BrokerStateStore requires BrokerState."
            )

        key = (
            state.account_fingerprint,
            state.symbol,
        )

        self._states[key] = state

        if agent_id is None:
            return

        normalized_agent_id = (
            self._normalize_agent_id(
                agent_id
            )
        )

        received_at = self._clock()

        if not isinstance(
            received_at,
            datetime,
        ):
            raise TypeError(
                "clock must return datetime."
            )

        if received_at.tzinfo is None:
            raise ValueError(
                "clock must return timezone-aware datetime."
            )

        self._agent_states[
            normalized_agent_id
        ] = state

        self._agent_received_at[
            normalized_agent_id
        ] = received_at.astimezone(
            UTC
        )

    def get(
        self,
        *,
        account_fingerprint: str,
        symbol: str,
    ) -> BrokerState | None:
        key = (
            account_fingerprint,
            symbol,
        )

        return self._states.get(
            key
        )

    def get_for_agent(
        self,
        *,
        agent_id: str,
    ) -> BrokerState | None:
        normalized_agent_id = (
            self._normalize_agent_id(
                agent_id
            )
        )

        return self._agent_states.get(
            normalized_agent_id
        )

    def get_received_at_for_agent(
        self,
        *,
        agent_id: str,
    ) -> datetime | None:
        normalized_agent_id = (
            self._normalize_agent_id(
                agent_id
            )
        )

        return self._agent_received_at.get(
            normalized_agent_id
        )