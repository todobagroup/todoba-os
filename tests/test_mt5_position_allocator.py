"""
TODOBA MT5 Position Allocator Tests
"""

import pytest

from backend.trading.broker.mt5_position_allocator import (
    MT5PositionAllocator,
)
from backend.trading.risk.position_sizing_request import (
    PositionSizingRequest,
)
from backend.trading.risk.risk_estimator import (
    RiskEstimator,
)


class FakeRiskEstimator(RiskEstimator):

    def __init__(
        self,
        *,
        loss_per_volume_step: float,
    ):
        self.loss_per_volume_step = (
            loss_per_volume_step
        )

    def estimate_expected_loss(
        self,
        *,
        symbol,
        order_type,
        entry_price,
        stop_loss,
        volume,
    ):
        return (
            volume / 0.01
        ) * self.loss_per_volume_step


def create_request(
    *,
    minimum_volume=0.01,
    volume_step=0.01,
    maximum_volume=1.0,
):
    return PositionSizingRequest(
        account_equity=5000.0,
        symbol="XAUUSD",
        order_type="BUY",
        entry_price=4010.0,
        stop_loss=3990.0,
        minimum_volume=minimum_volume,
        volume_step=volume_step,
        maximum_volume=maximum_volume,
    )


def test_returns_largest_volume_within_budget():

    allocator = MT5PositionAllocator(
        risk_estimator=FakeRiskEstimator(
            loss_per_volume_step=10.0,
        )
    )

    volume = allocator.allocate(
        request=create_request(),
        risk_budget_money=25.0,
    )

    assert volume == pytest.approx(
        0.02
    )


def test_returns_exact_volume_at_budget():

    allocator = MT5PositionAllocator(
        risk_estimator=FakeRiskEstimator(
            loss_per_volume_step=10.0,
        )
    )

    volume = allocator.allocate(
        request=create_request(),
        risk_budget_money=30.0,
    )

    assert volume == pytest.approx(
        0.03
    )


def test_returns_zero_when_minimum_volume_exceeds_budget():

    allocator = MT5PositionAllocator(
        risk_estimator=FakeRiskEstimator(
            loss_per_volume_step=20.0,
        )
    )

    volume = allocator.allocate(
        request=create_request(),
        risk_budget_money=10.0,
    )

    assert volume == 0.0


def test_never_exceeds_maximum_volume():

    allocator = MT5PositionAllocator(
        risk_estimator=FakeRiskEstimator(
            loss_per_volume_step=1.0,
        )
    )

    volume = allocator.allocate(
        request=create_request(
            maximum_volume=0.05,
        ),
        risk_budget_money=1000.0,
    )

    assert volume == pytest.approx(
        0.05
    )