"""
TODOBA Trading Execution Adapter

Converts TradingIntent into ExecutionPlan while
preserving the complete order type.
"""

from backend.trading.execution.execution_plan import (
    ExecutionPlan,
)
from backend.trading.intent.trading_intent import (
    TradingIntent,
)


class TradingExecutionAdapter:
    """
    Convert TradingIntent into ExecutionPlan.
    """

    def to_execution_plan(
        self,
        intent: TradingIntent,
    ) -> ExecutionPlan:
        if not isinstance(
            intent,
            TradingIntent,
        ):
            raise TypeError(
                "TradingExecutionAdapter requires "
                "TradingIntent."
            )

        return ExecutionPlan(
            symbol=intent.asset,
            order_type=intent.order_type,
            entry=intent.entry,
            sl=intent.sl,
            tp=intent.tp,
            lot=None,
            magic_number=10001,
            comment="TODOBA",
        )