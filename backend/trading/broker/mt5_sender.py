"""
TODOBA MT5 Sender

Sends MT5 order requests and normalizes broker results.
"""

import MetaTrader5 as mt5

from backend.trading.models.order_result import (
    OrderResult,
)


class MT5Sender:

    def __init__(
        self,
        *,
        mt5_module=mt5,
    ):
        self.mt5 = mt5_module

    def send(
        self,
        request,
    ) -> OrderResult:

        result = self.mt5.order_send(
            request
        )

        if result is None:
            raise RuntimeError(
                "MT5 order_send returned None."
            )

        success = result.retcode in (
            self.mt5.TRADE_RETCODE_DONE,
            self.mt5.TRADE_RETCODE_PLACED,
        )

        return OrderResult(
            success=success,
            retcode=result.retcode,
            order=result.order,
            deal=result.deal,
            volume=result.volume,
            price=result.price,
            comment=result.comment,
        )