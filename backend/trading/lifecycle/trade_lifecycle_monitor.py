"""
TODOBA Trade Lifecycle Monitor

Observes registered MT5 positions and completes the
organizational trading lifecycle after a position closes.
"""

from dataclasses import dataclass
from typing import Any, Optional

import MetaTrader5 as mt5

from backend.trading.lifecycle.mt5_trade_history_reader import (
    MT5TradeHistoryReader,
)
from backend.trading.lifecycle.open_trade_persistence import (
    OpenTradePersistence,
)
from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)
from backend.trading.lifecycle.trade_reflection_pipeline import (
    TradeReflectionPipeline,
    TradeReflectionResult,
)
from backend.trading.lifecycle.trade_status import TradeStatus


@dataclass(frozen=True)
class TradeLifecycleMonitorResult:
    status: str
    trade_id: str
    position_id: int
    reflection: Optional[
        TradeReflectionResult
    ] = None
    errors: tuple[str, ...] = ()


class TradeLifecycleMonitor:
    """
    Monitor open trades and complete their lifecycle.
    """

    def __init__(
        self,
        *,
        registry: OpenTradeRegistry,
        history_reader: MT5TradeHistoryReader,
        reflection_pipeline: TradeReflectionPipeline,
        persistence: Optional[
            OpenTradePersistence
        ] = None,
        mt5_module=mt5,
    ):
        if not isinstance(
            registry,
            OpenTradeRegistry,
        ):
            raise TypeError(
                "TradeLifecycleMonitor requires "
                "OpenTradeRegistry."
            )

        if not isinstance(
            history_reader,
            MT5TradeHistoryReader,
        ):
            raise TypeError(
                "TradeLifecycleMonitor requires "
                "MT5TradeHistoryReader."
            )

        if not isinstance(
            reflection_pipeline,
            TradeReflectionPipeline,
        ):
            raise TypeError(
                "TradeLifecycleMonitor requires "
                "TradeReflectionPipeline."
            )

        if (
            persistence is not None
            and not isinstance(
                persistence,
                OpenTradePersistence,
            )
        ):
            raise TypeError(
                "persistence must be "
                "OpenTradePersistence."
            )

        self.registry = registry
        self.history_reader = history_reader
        self.reflection_pipeline = (
            reflection_pipeline
        )
        self.persistence = persistence
        self.mt5 = mt5_module

    def check_trade(
        self,
        trade_id: str,
    ) -> TradeLifecycleMonitorResult:
        tracked_trade = self.registry.get(
            trade_id
        )

        if tracked_trade is None:
            raise LookupError(
                f"Trade is not registered: {trade_id}"
            )

        try:
            positions = self.mt5.positions_get(
                ticket=tracked_trade.position_id
            )

            if positions is None:
                raise RuntimeError(
                    "MT5 positions_get failed: "
                    f"{self._read_last_error()}"
                )

            if len(positions) > 0:
                return TradeLifecycleMonitorResult(
                    status="open",
                    trade_id=trade_id,
                    position_id=(
                        tracked_trade.position_id
                    ),
                )

            observation = (
                self.history_reader
                .read_closed_position(
                    tracked_trade.position_id
                )
            )

            if observation is None:
                return TradeLifecycleMonitorResult(
                    status="awaiting_history",
                    trade_id=trade_id,
                    position_id=(
                        tracked_trade.position_id
                    ),
                )

            tracked_trade.trade_record.status = (
                TradeStatus.CLOSED
            )

            reflection = (
                self.reflection_pipeline.reflect(
                    trade_record=(
                        tracked_trade.trade_record
                    ),
                    observation=observation,
                    context=tracked_trade.context,
                )
            )

            if self.persistence is not None:
                self.persistence.remove(
                    trade_id
                )
            else:
                self.registry.remove(
                    trade_id
                )

            return TradeLifecycleMonitorResult(
                status="reflected",
                trade_id=trade_id,
                position_id=(
                    tracked_trade.position_id
                ),
                reflection=reflection,
            )

        except Exception as error:
            return TradeLifecycleMonitorResult(
                status="monitor_failed",
                trade_id=trade_id,
                position_id=(
                    tracked_trade.position_id
                ),
                errors=(str(error),),
            )

    def check_all(
        self,
    ) -> list[TradeLifecycleMonitorResult]:
        trade_ids = [
            tracked.trade_record.trade_id
            for tracked in self.registry.list()
        ]

        return [
            self.check_trade(
                trade_id
            )
            for trade_id in trade_ids
        ]

    def _read_last_error(self) -> Any:
        last_error = getattr(
            self.mt5,
            "last_error",
            None,
        )

        if callable(last_error):
            return last_error()

        return "unknown"