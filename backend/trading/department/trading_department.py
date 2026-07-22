"""
TODOBA Trading Department

The Trading Department is the single owner of shared
organizational trading infrastructure.

External integrations must use the department instead of
constructing trading infrastructure directly.
"""

from pathlib import Path

import MetaTrader5 as mt5

from backend.brain.memory import MemoryEngine
from backend.trading.lifecycle.mt5_position_identity_resolver import (
    MT5PositionIdentityResolver,
)
from backend.trading.lifecycle.mt5_trade_history_reader import (
    MT5TradeHistoryReader,
)
from backend.trading.lifecycle.open_trade_persistence import (
    OpenTradePersistence,
)
from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)
from backend.trading.lifecycle.open_trade_repository import (
    OpenTradeRepository,
)
from backend.trading.lifecycle.trade_lifecycle_monitor import (
    TradeLifecycleMonitor,
)
from backend.trading.lifecycle.trade_lifecycle_scheduler import (
    TradeLifecycleScheduler,
)
from backend.trading.lifecycle.trade_memory_bridge import (
    TradeMemoryBridge,
)
from backend.trading.lifecycle.trade_reflection_pipeline import (
    TradeReflectionPipeline,
)
from backend.trading.lifecycle.trade_timeline_registry import (
    TradeTimelineRegistry,
)
from backend.trading.lifecycle.trade_timeline_service import (
    TradeTimelineService,
)
from backend.trading.pending.pending_activation_bridge import (
    PendingActivationBridge,
)
from backend.trading.pending.pending_activation_runtime import (
    PendingActivationRuntime,
)
from backend.trading.pending.pending_activation_scheduler import (
    PendingActivationScheduler,
)
from backend.trading.pending.pending_broker_evidence_reader import (
    PendingBrokerEvidenceReader,
)
from backend.trading.pending.pending_order_monitor import (
    PendingOrderMonitor,
)
from backend.trading.pending.pending_order_persistence import (
    PendingOrderPersistence,
)
from backend.trading.pending.pending_order_repository import (
    PendingOrderRepository,
)
from backend.trading.runtime.runtime_recovery import (
    RuntimeRecovery,
)
from backend.trading.runtime.trading_runtime import (
    TradingRuntime,
)


class TradingDepartment:
    """
    Assemble, own, start, and stop Trading capabilities.
    """

    def __init__(
        self,
        *,
        execution_pipeline,
        open_trades_storage_path: Path,
        memory: MemoryEngine,
        mt5_module=mt5,
        lifecycle_interval_seconds: float = 5.0,
    ):
        if execution_pipeline is None:
            raise ValueError(
                "TradingDepartment requires "
                "an execution pipeline."
            )

        if not isinstance(
            open_trades_storage_path,
            Path,
        ):
            raise TypeError(
                "open_trades_storage_path must be Path."
            )

        if not isinstance(
            memory,
            MemoryEngine,
        ):
            raise TypeError(
                "TradingDepartment requires MemoryEngine."
            )

        self.mt5 = mt5_module

        self.registry = OpenTradeRegistry()

        self.timeline_registry = (
            TradeTimelineRegistry()
        )

        self.timeline_service = (
            TradeTimelineService(
                self.timeline_registry
            )
        )

        self.repository = OpenTradeRepository(
            open_trades_storage_path
        )

        self.position_resolver = (
            MT5PositionIdentityResolver(
                mt5_module
            )
        )

        self.persistence = OpenTradePersistence(
            registry=self.registry,
            repository=self.repository,
            position_resolver=self.position_resolver,
        )

        self.recovery = RuntimeRecovery(
            repository=self.repository,
            registry=self.registry,
        )

        self.pending_repository = (
            PendingOrderRepository()
        )

        pending_orders_storage_path = (
            open_trades_storage_path.parent
            / "pending_orders.json"
        )

        self.pending_persistence = (
            PendingOrderPersistence(
                pending_orders_storage_path
            )
        )

        self.pending_monitor = (
            PendingOrderMonitor(
                repository=self.pending_repository,
                mt5_module=mt5_module,
            )
        )

        self.pending_evidence_reader = (
            PendingBrokerEvidenceReader(
                mt5_module
            )
        )

        self.pending_activation_bridge = (
            PendingActivationBridge()
        )

        self.pending_restored_count = 0

        self.memory_bridge = TradeMemoryBridge(
            memory
        )

        self.reflection_pipeline = (
            TradeReflectionPipeline(
                memory_bridge=self.memory_bridge
            )
        )

        self.history_reader = (
            MT5TradeHistoryReader(
                mt5_module
            )
        )

        self.lifecycle_monitor = (
            TradeLifecycleMonitor(
                registry=self.registry,
                history_reader=self.history_reader,
                reflection_pipeline=(
                    self.reflection_pipeline
                ),
                persistence=self.persistence,
                mt5_module=mt5_module,
            )
        )

        self.lifecycle_scheduler = (
            TradeLifecycleScheduler(
                monitor=self.lifecycle_monitor,
                interval_seconds=(
                    lifecycle_interval_seconds
                ),
            )
        )

        self.runtime = TradingRuntime(
            execution_pipeline=execution_pipeline,
            open_trade_persistence=self.persistence,
            timeline_service=self.timeline_service,
            pending_order_repository=(
                self.pending_repository
            ),
            pending_order_persistence=(
                self.pending_persistence
            ),
        )

        self.pending_activation_runtime = (
            PendingActivationRuntime(
                repository=self.pending_repository,
                evidence_reader=(
                    self.pending_evidence_reader
                ),
                activation_bridge=(
                    self.pending_activation_bridge
                ),
                trading_runtime=self.runtime,
            )
        )

        self.pending_activation_scheduler = (
            PendingActivationScheduler(
                runtime=(
                    self.pending_activation_runtime
                ),
                interval_seconds=(
                    lifecycle_interval_seconds
                ),
            )
        )

        self.running = False

    async def start(self) -> int:
        """
        Recover state and start the Trading Department.
        """

        if self.running:
            return 0

        restored_trade_count = (
            self.recovery.restore()
        )

        self.pending_restored_count = (
            self.pending_persistence.restore(
                self.pending_repository
            )
        )

        self.runtime.start()

        await self.lifecycle_scheduler.start()

        await (
            self.pending_activation_scheduler.start()
        )

        self.running = True

        return restored_trade_count

    async def stop(self) -> bool:
        """
        Stop the Trading Department cleanly.
        """

        if not self.running:
            return True

        await (
            self.pending_activation_scheduler.stop()
        )

        await self.lifecycle_scheduler.stop()

        self.pending_persistence.save(
            self.pending_repository
        )

        self.runtime.stop()

        self.running = False

        return True