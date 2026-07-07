"""
TODOBA Execution Validator

Validates an order before sending to MT5.
"""


class ExecutionValidator:

    def validate(
        self,
        *,
        symbol,
        volume,
        order_type,
        price,
        sl,
        tp,
    ):

        if not symbol:
            raise ValueError("Symbol is required.")

        if volume <= 0:
            raise ValueError("Volume must be greater than zero.")

        if order_type not in ("BUY", "SELL"):
            raise ValueError("Unsupported order type.")

        if price <= 0:
            raise ValueError("Invalid price.")

        if sl <= 0:
            raise ValueError("Invalid stop loss.")

        if tp <= 0:
            raise ValueError("Invalid take profit.")

        if order_type == "BUY":

            if sl >= price:
                raise ValueError("BUY: SL must be below entry.")

            if tp <= price:
                raise ValueError("BUY: TP must be above entry.")

        if order_type == "SELL":

            if sl <= price:
                raise ValueError("SELL: SL must be above entry.")

            if tp >= price:
                raise ValueError("SELL: TP must be below entry.")

        return True