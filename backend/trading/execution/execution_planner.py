"""
TODOBA Execution Planner
"""

from backend.trading.execution.execution_plan import ExecutionPlan


def create_plan(signal, profile) -> ExecutionPlan:

    return ExecutionPlan(
        symbol=signal.symbol,
        order_type=signal.order_type,
        entry=signal.entry,
        sl=signal.sl,
        tp=signal.tp,
        lot=None,
        magic_number=10001,
        comment="TODOBA",
    )
    