"""
TODOBA Runtime Bootstrap

Owns the construction and lifecycle composition
of Trading infrastructure.

Responsibilities:
- Build TradingProfile
- Build LiveExecutionPipeline
- Build TradingDepartment
- Build TelegramTaskProducer
- Build TelegramTaskExecutionBridge
- Build MT5 infrastructure
- Compose Trading startup and shutdown
- Register lifecycle services with TODOBARuntime

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
from backend.trading.broker.mt5_client import MT5Client
from backend.trading.broker.mt5_safety import MT5Safety
from backend.trading.department.runtime_health_factory import (
    RuntimeHealthFactory,
)
from backend.trading.department.trading_department import (
    TradingDepartment,
)
from backend.trading.execution.live_execution_pipeline import (
    LiveExecutionPipeline,
)
from backend.trading.profile.trading_profile import (
    TradingProfile,
)
from backend.trading.runtime.runtime_health_console import (
    print_runtime_health,
)


OPEN_TRADES_STORAGE_PATH = (
    BASE_DIR
    / "data"
    / "trading"
    / "open_trades.json"
)


class RuntimeBootstrap:
    """
    Constructs and composes the Trading infrastructure
    required by TODOBA.
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

        self.mt5_client = MT5Client()

        self.restored_trade_count = 0
        self.started = False

    async def _start_trading_runtime(self) -> None:
        if self.started:
            return

        if not self.mt5_client.connect():
            raise RuntimeError(
                "TODOBA could not connect to MT5."
            )

        try:
            MT5Safety().validate()

            account = self.mt5_client.get_account_info()

            if account is None:
                raise RuntimeError(
                    "TODOBA could not read MT5 account."
                )

            self.restored_trade_count = (
                await self.department.start()
            )

            health_report = RuntimeHealthFactory().build(
                department=self.department,
                restored_trade_count=(
                    self.restored_trade_count
                ),
                mt5_ready=self.mt5_client.is_connected(),
            )

            print("MT5 Connection: READY")
            print(
                f"MT5 Account: "
                f"{account.login}"
            )
            print(
                f"MT5 Server: "
                f"{account.server}"
            )
            print(
                f"Maximum Open Trades: "
                f"{self.profile.max_open_trades}"
            )

            print_runtime_health(
                health_report
            )

            if not health_report.healthy:
                raise RuntimeError(
                    "TODOBA system health check failed."
                )

            self.started = True

        except Exception:
            await self.department.stop()
            self.mt5_client.disconnect()
            raise

    async def _stop_trading_runtime(self) -> None:
        if not self.started:
            return

        try:
            await self.department.stop()
        finally:
            self.mt5_client.disconnect()
            self.started = False

    def create_runtime(self) -> TODOBARuntime:
        """
        Create TODOBARuntime and register
        the composed Trading lifecycle.
        """

        runtime = TODOBARuntime()

        runtime.register(
            start=self._start_trading_runtime,
            stop=self._stop_trading_runtime,
        )

        return runtime