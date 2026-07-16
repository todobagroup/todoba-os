"""
TODOBA Runtime Recovery

Restores the Trading Runtime after restart.

Architecture:

TradingRuntime
        │
        ▼
RuntimeRecovery
        │
        ▼
OpenTradeRepository
        │
        ▼
OpenTradeRegistry

Responsibility:

- Restore tracked trades from durable storage.
- Rebuild the in-memory registry.
- Do not communicate with MT5.
- Do not start the scheduler.
"""


from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)
from backend.trading.lifecycle.open_trade_repository import (
    OpenTradeRepository,
)


class RuntimeRecovery:
    """
    Restore runtime state from persistent storage.
    """

    def __init__(
        self,
        *,
        repository: OpenTradeRepository,
        registry: OpenTradeRegistry,
    ):

        if not isinstance(
            repository,
            OpenTradeRepository,
        ):
            raise TypeError(
                "RuntimeRecovery requires "
                "OpenTradeRepository."
            )

        if not isinstance(
            registry,
            OpenTradeRegistry,
        ):
            raise TypeError(
                "RuntimeRecovery requires "
                "OpenTradeRegistry."
            )

        self.repository = repository
        self.registry = registry

    def restore(
        self,
    ) -> int:
        """
        Restore tracked trades into the registry.

        Returns
        -------
        int
            Number of restored trades.
        """

        trades = self.repository.load()

        for tracked in trades:

            self.registry.register(
                trade_record=tracked.trade_record,
                position_id=tracked.position_id,
                context=tracked.context,
            )

        return len(trades)