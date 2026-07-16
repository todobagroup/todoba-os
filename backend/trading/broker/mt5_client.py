"""
TODOBA MT5 Client

Connects TODOBA to MetaTrader 5.
"""

import time

import MetaTrader5 as mt5

from backend.trading.broker.broker_client import (
    BrokerClient,
)
from backend.trading.models.account_info import (
    AccountInfo,
)
from backend.trading.models.market_info import (
    MarketInfo,
)


class MT5Client(BrokerClient):

    def __init__(
        self,
        *,
        mt5_module=mt5,
    ):
        self.mt5 = mt5_module

    def connect(self) -> bool:
        return bool(
            self.mt5.initialize()
        )

    def disconnect(self) -> None:
        self.mt5.shutdown()

    def is_connected(self) -> bool:
        return (
            self.mt5.terminal_info()
            is not None
        )

    def reconnect(
        self,
        *,
        max_attempts: int = 3,
        delay_seconds: float = 0.0,
    ) -> bool:
        if max_attempts <= 0:
            raise ValueError(
                "max_attempts must be greater than zero."
            )

        if delay_seconds < 0:
            raise ValueError(
                "delay_seconds cannot be negative."
            )

        for attempt in range(max_attempts):
            if self.is_connected():
                return True

            self.disconnect()

            if self.connect():
                return True

            if (
                delay_seconds > 0
                and attempt < max_attempts - 1
            ):
                time.sleep(
                    delay_seconds
                )

        return False

    def execute(self, request):
        raise NotImplementedError(
            "Execution not implemented."
        )

    def get_account_info(self):

        info = self.mt5.account_info()

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

    def get_market_info(
        self,
        symbol,
    ):
        symbol_info = self.mt5.symbol_info(
            symbol
        )

        tick = self.mt5.symbol_info_tick(
            symbol
        )

        if (
            symbol_info is None
            or tick is None
        ):
            return None

        spread = (
            tick.ask - tick.bid
        ) / symbol_info.point

        return MarketInfo(
            symbol=symbol,
            bid=tick.bid,
            ask=tick.ask,
            spread=spread,
            digits=symbol_info.digits,
            point=symbol_info.point,
        )