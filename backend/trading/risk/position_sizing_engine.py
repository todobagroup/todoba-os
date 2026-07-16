"""
TODOBA Position Sizing Engine

Stable V1 implementation.

Position sizing is determined by
the Stable Lot Policy.
"""

from backend.trading.risk.position_sizing_result import (
    PositionSizingResult,
)
from backend.trading.risk.stable_lot_policy import (
    calculate_stable_lot,
)


class PositionSizingEngine:
    """
    Stable Position Sizing Engine.

    Entry, SL and TP are provided by the
    Strategy Department.

    This engine only decides the position size.
    """

    def evaluate(
        self,
        *,
        account_equity: float,
    ) -> PositionSizingResult:

        lot = calculate_stable_lot(
            equity=account_equity,
        )

        return PositionSizingResult(
            approved=lot.approved,
            volume=lot.volume,
            estimated_risk_money=0.0,
            estimated_risk_percent=0.0,
            reason=lot.reason,
        )