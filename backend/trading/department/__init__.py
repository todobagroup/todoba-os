"""
TODOBA Trading Department

Purpose:

Trading Department is the single owner of all
organizational trading infrastructure.

It assembles, owns, starts, stops, and exposes the
Trading Runtime.

External integrations such as Telegram, REST API,
Dashboard, or AI Trader must not construct trading
infrastructure directly.

Responsibilities:

- Own TradingRuntime.
- Own OpenTradeRegistry.
- Own OpenTradeRepository.
- Own OpenTradePersistence.
- Own RuntimeRecovery.
- Own TradeLifecycleMonitor.
- Own TradeLifecycleScheduler.
- Expose runtime.
- Start the department.
- Stop the department.

Non-responsibilities:

- Parse Telegram messages.
- Make trading decisions.
- Read MT5 market prices.
- Execute MT5 orders directly.
- Store Brain memories.
"""

from pathlib import Path

from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)
from backend.trading.lifecycle.open_trade_repository import (
    OpenTradeRepository,
)
from backend.trading.runtime.runtime_recovery import (
    RuntimeRecovery,
)


class TradingDepartment:
    """
    Own the complete Trading Department infrastructure.
    """

    def __init__(
        self,
        *,
        open_trades_storage_path: Path,
    ):
        self.registry = OpenTradeRegistry()

        self.repository = OpenTradeRepository(
            open_trades_storage_path
        )

        self.recovery = RuntimeRecovery(
            repository=self.repository,
            registry=self.registry,
        )

        self.runtime = None
        self.persistence = None
        self.lifecycle_monitor = None
        self.lifecycle_scheduler = None

    def start(self) -> bool:
        """
        Start the Trading Department.
        """

        return True

    def stop(self) -> bool:
        """
        Stop the Trading Department.
        """

        return True