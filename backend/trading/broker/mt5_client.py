"""
TODOBA MT5 Client

Connects TODOBA to MetaTrader 5.
"""

import MetaTrader5 as mt5

from backend.trading.broker.broker_client import BrokerClient
from backend.trading.models.account_info import AccountInfo
from backend.trading.models.market_info import MarketInfo


class MT5Client(BrokerClient):

    def connect(self):
        return mt5.initialize()

    def disconnect(self):
        mt5.shutdown()

    def is_connected(self):
        return mt5.terminal_info() is not None

    def execute(self, request):
        raise NotImplementedError("Execution not implemented.")

    def get_account_info(self):

        info = mt5.account_info()

        if info is None:
            return None

        return AccountInfo(
            login=info.login,
            server=info.server,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            leverage=info.leverage,
        )

    def get_market_info(self, symbol):

        symbol_info = mt5.symbol_info(symbol)

        tick = mt5.symbol_info_tick(symbol)

        if symbol_info is None or tick is None:
            return None

        spread = (tick.ask - tick.bid) / symbol_info.point

        return MarketInfo(
            symbol=symbol,
            bid=tick.bid,
            ask=tick.ask,
            spread=spread,
            digits=symbol_info.digits,
            point=symbol_info.point,
        )