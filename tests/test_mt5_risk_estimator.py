"""
TODOBA MT5 Risk Estimator Tests
"""

import pytest

from backend.trading.broker.mt5_risk_estimator import (
    MT5RiskEstimator,
)


class FakeMT5:

    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def order_calc_profit(
        self,
        order_type,
        symbol,
        volume,
        entry,
        close,
    ):
        return -19.42


def test_buy_loss_is_positive():

    estimator = MT5RiskEstimator(
        mt5_module=FakeMT5(),
    )

    loss = estimator.estimate_expected_loss(
        symbol="XAUUSD",
        order_type="BUY",
        entry_price=4010.0,
        stop_loss=3990.0,
        volume=0.01,
    )

    assert loss == pytest.approx(
        19.42
    )


def test_sell_loss_is_positive():

    estimator = MT5RiskEstimator(
        mt5_module=FakeMT5(),
    )

    loss = estimator.estimate_expected_loss(
        symbol="XAUUSD",
        order_type="SELL",
        entry_price=3990.0,
        stop_loss=4010.0,
        volume=0.01,
    )

    assert loss == pytest.approx(
        19.42
    )


def test_invalid_order_type():

    estimator = MT5RiskEstimator(
        mt5_module=FakeMT5(),
    )

    with pytest.raises(ValueError):

        estimator.estimate_expected_loss(
            symbol="XAUUSD",
            order_type="HOLD",
            entry_price=1,
            stop_loss=1,
            volume=0.01,
        )