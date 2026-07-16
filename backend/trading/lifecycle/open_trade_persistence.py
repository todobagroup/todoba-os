"""
TODOBA Open Trade Persistence

Keeps the open-trade registry and durable repository
synchronized.
"""

from typing import Optional

from backend.trading.lifecycle.mt5_position_identity_resolver import (
    MT5PositionIdentityResolver,
)
from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
    TrackedTrade,
)
from backend.trading.lifecycle.open_trade_repository import (
    OpenTradeRepository,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)


class OpenTradePersistence:
    """
    Synchronize open trades between runtime memory
    and durable storage.
    """

    def __init__(
        self,
        *,
        registry: OpenTradeRegistry,
        repository: OpenTradeRepository,
        position_resolver: MT5PositionIdentityResolver,
    ):
        if not isinstance(
            registry,
            OpenTradeRegistry,
        ):
            raise TypeError(
                "OpenTradePersistence requires "
                "OpenTradeRegistry."
            )

        if not isinstance(
            repository,
            OpenTradeRepository,
        ):
            raise TypeError(
                "OpenTradePersistence requires "
                "OpenTradeRepository."
            )

        if not isinstance(
            position_resolver,
            MT5PositionIdentityResolver,
        ):
            raise TypeError(
                "OpenTradePersistence requires "
                "MT5PositionIdentityResolver."
            )

        self.registry = registry
        self.repository = repository
        self.position_resolver = position_resolver

    def persist(
        self,
        trade_record: TradeRecord,
        *,
        context: Optional[dict] = None,
    ) -> TrackedTrade:
        """
        Register a newly opened trade and persist
        the complete registry.
        """

        if not isinstance(
            trade_record,
            TradeRecord,
        ):
            raise TypeError(
                "persist requires TradeRecord."
            )

        position_id = self.position_resolver.resolve(
            trade_record
        )

        tracked_trade = self.registry.register(
            trade_record=trade_record,
            position_id=position_id,
            context=context or {},
        )

        self.sync()

        return tracked_trade

    def remove(
        self,
        trade_id: str,
    ) -> Optional[TrackedTrade]:
        """
        Remove a closed trade and persist the
        remaining open trades.
        """

        if not isinstance(
            trade_id,
            str,
        ):
            raise TypeError(
                "trade_id must be a string."
            )

        if not trade_id:
            raise ValueError(
                "trade_id cannot be empty."
            )

        tracked_trade = self.registry.get(
            trade_id
        )

        if tracked_trade is None:
            return None

        self.registry.remove(
            trade_id
        )

        self.sync()

        return tracked_trade

    def sync(self) -> None:
        """
        Persist the complete current registry.
        """

        self.repository.save(
            self.registry.list()
        )