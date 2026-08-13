"""
TODOBA Broker State Store

Stores the latest BrokerState observed for each
account and symbol.

This component owns in-memory broker-state lookup only.
"""

from backend.trading.execution.broker_state import (
    BrokerState,
)


class BrokerStateStore:
    """
    Store the latest broker state by
    account fingerprint and symbol.
    """

    def __init__(self) -> None:
        self._states: dict[
            tuple[str, str],
            BrokerState,
        ] = {}

    def save(
        self,
        state: BrokerState,
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