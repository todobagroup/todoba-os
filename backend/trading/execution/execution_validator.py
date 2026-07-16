"""
TODOBA Execution Validator

Validates an order before sending to MT5.
"""


class ExecutionValidator:

    MARKET_ORDERS = (
        "BUY",
        "SELL",
    )

    PENDING_ORDERS = (
        "BUY LIMIT",
        "SELL LIMIT",
        "BUY STOP",
        "SELL STOP",
    )

    SUPPORTED_ORDER_TYPES = (
        *MARKET_ORDERS,
        *PENDING_ORDERS,
    )

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
            raise ValueError(
                "Symbol is required."
            )

        if volume <= 0:
            raise ValueError(
                "Volume must be greater than zero."
            )

        order_type = (
            order_type
            .strip()
            .upper()
        )

        if (
            order_type
            not in self.SUPPORTED_ORDER_TYPES
        ):
            raise ValueError(
                "Unsupported order type."
            )

        if price <= 0:
            raise ValueError(
                "Invalid price."
            )

        if sl <= 0:
            raise ValueError(
                "Invalid stop loss."
            )

        if tp <= 0:
            raise ValueError(
                "Invalid take profit."
            )

        buy_orders = (
            "BUY",
            "BUY LIMIT",
            "BUY STOP",
        )

        sell_orders = (
            "SELL",
            "SELL LIMIT",
            "SELL STOP",
        )

        if order_type in buy_orders:

            if sl >= price:
                raise ValueError(
                    "BUY: SL must be below entry."
                )

            if tp <= price:
                raise ValueError(
                    "BUY: TP must be above entry."
                )

        elif order_type in sell_orders:

            if sl <= price:
                raise ValueError(
                    "SELL: SL must be above entry."
                )

            if tp >= price:
                raise ValueError(
                    "SELL: TP must be below entry."
                )

        return True