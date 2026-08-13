"""
TODOBA Broker State Store

Stores the latest BrokerState observed for each
account, symbol, and authenticated Trusted Agent.

This component owns in-memory broker-state lookup only.
"""

from backend.trading.execution.broker_state import (
    BrokerState,
)


class BrokerStateStore:
    """
    Store the latest broker state by account and agent.
    """

    def __init__(self) -> None:
        self._states: dict[
            tuple[str, str],
            BrokerState,
        ] = {}

        self._agent_states: dict[
            str,
            BrokerState,
        ] = {}

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

        self._agent_states[
            normalized_agent_id
        ] = state

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

        return self._agent_states.get(
            normalized_agent_id
        )