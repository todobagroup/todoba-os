"""
TODOBA Execution Planner
"""

from backend.trading.execution.execution_plan import ExecutionPlan
from backend.trading.execution.lot_calculator import calculate


def create_plan(signal, profile) -> ExecutionPlan:

    lot = calculate(profile.lot_policy_name)

    return ExecutionPlan(
        symbol=signal.symbol,
        order_type=signal.order_type,
        entry=signal.entry,
        sl=signal.sl,
        tp=signal.tp,
        lot=lot,
        magic_number=10001,
        comment="TODOBA",
    )