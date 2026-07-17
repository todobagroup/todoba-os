"""
TODOBA MT5 Order Builder

Builds MT5 order requests for market
and pending orders.
"""

import MetaTrader5 as mt5


class MT5OrderBuilder:

    def __init__(
        self,
        *,
        mt5_module=mt5,
    ):
        self.mt5 = mt5_module

    def build(
        self,
        *,
        symbol,
        volume,
        order_type,
        price,
        sl,
        tp,
        comment="TODOBA",
    ):

        order_types = {
            "BUY": self.mt5.ORDER_TYPE_BUY,
            "SELL": self.mt5.ORDER_TYPE_SELL,
            "BUY LIMIT": (
                self.mt5.ORDER_TYPE_BUY_LIMIT
            ),
            "SELL LIMIT": (
                self.mt5.ORDER_TYPE_SELL_LIMIT
            ),
            "BUY STOP": (
                self.mt5.ORDER_TYPE_BUY_STOP
            ),
            "SELL STOP": (
                self.mt5.ORDER_TYPE_SELL_STOP
            ),
        }

        if order_type not in order_types:
            raise ValueError(
                f"Unsupported order type: "
                f"{order_type}"
            )

        pending_order_types = {
            "BUY LIMIT",
            "SELL LIMIT",
            "BUY STOP",
            "SELL STOP",
        }

        is_pending = (
            order_type in pending_order_types
        )

        return {
            "action": (
                self.mt5.TRADE_ACTION_PENDING
                if is_pending
                else self.mt5.TRADE_ACTION_DEAL
            ),
            "symbol": symbol,
            "volume": volume,
            "type": order_types[order_type],
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 10001,
            "comment": comment,
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": (
                self.mt5.ORDER_FILLING_RETURN
                if is_pending
                else self.mt5.ORDER_FILLING_IOC
            ),
        }