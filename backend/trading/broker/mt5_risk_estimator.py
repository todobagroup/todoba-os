"""
TODOBA MT5 Risk Estimator

MT5 implementation of the RiskEstimator interface.
"""

import MetaTrader5 as mt5

from backend.trading.risk.risk_estimator import (
    RiskEstimator,
)


class MT5RiskEstimator(
    RiskEstimator,
):
    """
    Broker-specific risk estimation using MT5.
    """

    def __init__(
        self,
        *,
        mt5_module=mt5,
    ):
        self.mt5 = mt5_module

    def estimate_expected_loss(
        self,
        *,
        symbol: str,
        order_type: str,
        entry_price: float,
        stop_loss: float,
        volume: float,
    ) -> float:

        if order_type == "BUY":
            mt5_order_type = (
                self.mt5.ORDER_TYPE_BUY
            )

        elif order_type == "SELL":
            mt5_order_type = (
                self.mt5.ORDER_TYPE_SELL
            )

        else:
            raise ValueError(
                f"Unsupported order type: "
                f"{order_type}"
            )

        result = self.mt5.order_calc_profit(
            mt5_order_type,
            symbol,
            volume,
            entry_price,
            stop_loss,
        )

        if result is None:
            raise RuntimeError(
                "MT5 failed to estimate loss."
            )

        return abs(
            float(result)
        )