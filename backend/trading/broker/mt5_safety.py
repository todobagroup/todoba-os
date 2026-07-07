"""
TODOBA MT5 Safety Check

Checks whether MT5 is ready before sending an order.
"""

import MetaTrader5 as mt5


class MT5Safety:

    def validate(self):

        terminal = mt5.terminal_info()

        if terminal is None:
            raise RuntimeError("Cannot read terminal information.")

        if not terminal.connected:
            raise RuntimeError("MT5 is not connected.")

        if not terminal.trade_allowed:
            raise RuntimeError("AutoTrading is disabled.")

        return True