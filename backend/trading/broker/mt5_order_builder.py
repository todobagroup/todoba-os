"""
TODOBA MT5 Order Builder

Builds MT5 order requests for market
and pending orders.
"""

import MetaTrader5 as mt5


class MT5OrderBuilder:

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
            "BUY": mt5.ORDER_TYPE_BUY,
            "SELL": mt5.ORDER_TYPE_SELL,
            "BUY LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
            "SELL LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
            "BUY STOP": mt5.ORDER_TYPE_BUY_STOP,
            "SELL STOP": mt5.ORDER_TYPE_SELL_STOP,
        }

        if order_type not in order_types:
            raise ValueError(
                f"Unsupported order type: {order_type}"
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
                mt5.TRADE_ACTION_PENDING
                if is_pending
                else mt5.TRADE_ACTION_DEAL
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
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": (
                mt5.ORDER_FILLING_RETURN
                if is_pending
                else mt5.ORDER_FILLING_IOC
            ),
        }