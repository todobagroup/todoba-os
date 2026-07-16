"""
TODOBA MT5 Position Allocator

Finds the largest broker volume that remains
within the organizational risk budget.
"""

from backend.trading.risk.position_allocator import (
    PositionAllocator,
)
from backend.trading.risk.position_sizing_request import (
    PositionSizingRequest,
)
from backend.trading.risk.risk_estimator import (
    RiskEstimator,
)


class MT5PositionAllocator(
    PositionAllocator,
):
    """
    Allocate broker volume using broker-estimated loss.
    """

    def __init__(
        self,
        *,
        risk_estimator: RiskEstimator,
    ):
        if not isinstance(
            risk_estimator,
            RiskEstimator,
        ):
            raise TypeError(
                "MT5PositionAllocator requires "
                "RiskEstimator."
            )

        self.risk_estimator = risk_estimator

    def allocate(
        self,
        *,
        request: PositionSizingRequest,
        risk_budget_money: float,
    ) -> float:
        if risk_budget_money <= 0:
            raise ValueError(
                "risk_budget_money must be greater than zero."
            )

        if request.minimum_volume <= 0:
            raise ValueError(
                "minimum_volume must be greater than zero."
            )

        if request.volume_step <= 0:
            raise ValueError(
                "volume_step must be greater than zero."
            )

        if (
            request.maximum_volume
            < request.minimum_volume
        ):
            raise ValueError(
                "maximum_volume must be greater than "
                "or equal to minimum_volume."
            )

        volume = request.minimum_volume
        best_volume = 0.0

        while (
            volume
            <= request.maximum_volume + 1e-12
        ):
            loss = (
                self.risk_estimator
                .estimate_expected_loss(
                    symbol=request.symbol,
                    order_type=request.order_type,
                    entry_price=request.entry_price,
                    stop_loss=request.stop_loss,
                    volume=volume,
                )
            )

            if loss > risk_budget_money:
                break

            best_volume = volume

            volume = round(
                volume + request.volume_step,
                8,
            )

        return best_volume