"""
TODOBA Trading Execution Adapter

Converts TradingIntent into ExecutionPlan.
"""

from backend.trading.execution.execution_plan import ExecutionPlan


class TradingExecutionAdapter:

    def to_execution_plan(self, intent):

        return ExecutionPlan(
            symbol=intent.asset,
            order_type=f"{intent.action} NOW",
            entry=intent.entry,
            sl=intent.sl,
            tp=intent.tp,
            lot=None,
            magic_number=10001,
            comment="TODOBA",
        )