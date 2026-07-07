"""
TODOBA MT5 Sender

Sends MT5 order request and normalizes broker result.
"""

import MetaTrader5 as mt5

from backend.trading.models.order_result import OrderResult


class MT5Sender:

    def send(self, request) -> OrderResult:

        result = mt5.order_send(request)

        if result is None:
            raise RuntimeError("MT5 order_send returned None.")

        success = result.retcode in (
            mt5.TRADE_RETCODE_DONE,
            mt5.TRADE_RETCODE_PLACED,
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