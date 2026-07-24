"""
TODOBA Runtime Bootstrap

Owns the construction and runtime registration
of Trading infrastructure.

Responsibilities:
- Build TradingProfile
- Build LiveExecutionPipeline
- Build TradingDepartment
- Build TelegramTaskProducer
- Build TelegramTaskExecutionBridge
- Register lifecycle services with TODOBARuntime

RuntimeBootstrap does not directly start or stop services.
Lifecycle execution belongs to TODOBARuntime.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from backend.brain.memory import memory_engine
from backend.config import (
    BASE_DIR,
    MT5_BROKER_GOLD_SYMBOL,
)
from backend.integrations.telegram_task_execution_bridge import (
    TelegramTaskExecutionBridge,
)
from backend.integrations.telegram_task_producer import (
    TelegramTaskProducer,
)
from backend.runtime.todoba_runtime import TODOBARuntime
from backend.trading.department.trading_department import (
    TradingDepartment,
)
from backend.trading.execution.live_execution_pipeline import (
    LiveExecutionPipeline,
)
from backend.trading.profile.trading_profile import (
    TradingProfile,
)


OPEN_TRADES_STORAGE_PATH = (
    BASE_DIR
    / "data"
    / "trading"
    / "open_trades.json"
)


class RuntimeBootstrap:
    """
    Constructs the Trading infrastructure required by TODOBA.

    Construction belongs to RuntimeBootstrap.
    Lifecycle execution belongs to TODOBARuntime.
    """

    def __init__(self) -> None:
        self.profile = TradingProfile(
            profile_name="telegram_demo_gold",
            risk_percent=1.0,
            max_open_trades=10,
            allowed_symbols=("XAUUSD",),
            lot_policy_name="FIXED_001",
        )

        self.execution_pipeline = LiveExecutionPipeline(
            profile=self.profile,
            symbol_map={
                "XAUUSD": MT5_BROKER_GOLD_SYMBOL,
            },
        )

        self.department = TradingDepartment(
            execution_pipeline=self.execution_pipeline,
            open_trades_storage_path=OPEN_TRADES_STORAGE_PATH,
            memory=memory_engine,
            mt5_module=mt5,
            lifecycle_interval_seconds=5.0,
        )

        self.task_producer = TelegramTaskProducer(
            self.profile,
        )

        self.task_execution_bridge = (
            TelegramTaskExecutionBridge(
                producer=self.task_producer,
                department=self.department,
            )
        )

    def create_runtime(self) -> TODOBARuntime:
        """
        Create a TODOBA runtime and register owned lifecycle services.
        """
        runtime = TODOBARuntime()

        runtime.register(
            start=self.department.start,
            stop=self.department.stop,
        )

        return runtime