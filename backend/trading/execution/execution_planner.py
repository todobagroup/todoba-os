"""
TODOBA Execution Planner

Creates an immutable ExecutionPlan from an approved
trading Signal and TradingProfile.
"""

from backend.trading.execution.execution_plan import ExecutionPlan
from backend.trading.execution.lot_calculator import calculate
from backend.trading.models.signal import Signal
from backend.trading.profile.trading_profile import TradingProfile


def create_plan(
    signal: Signal,
    profile: TradingProfile,
) -> ExecutionPlan:
    """
    Create a broker-independent execution plan.

    This function does not send an order.
    """

    if signal is None:
        raise ValueError(
            "Signal is required."
        )

    if profile is None:
        raise ValueError(
            "Trading profile is required."
        )

    lot = calculate(
        profile.lot_policy_name
    )

    return ExecutionPlan(
        symbol=signal.symbol,
        order_type=signal.order_type,
        entry=signal.entry,
        sl=signal.sl,
        tp=signal.tp,
        lot=lot,
        magic_number=10001,
        comment=f"TODOBA:{profile.profile_name}",
    )