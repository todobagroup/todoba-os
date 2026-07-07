"""
TODOBA MT5 Order Builder

Builds MT5 order request from Execution Plan.
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

        if order_type == "BUY":
            mt5_type = mt5.ORDER_TYPE_BUY

        elif order_type == "SELL":
            mt5_type = mt5.ORDER_TYPE_SELL

        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        return {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 10001,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }