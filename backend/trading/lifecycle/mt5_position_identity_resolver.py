"""
TODOBA MT5 Position Identity Resolver

Resolves the MT5 position ID from the opening deal stored
inside a TradeRecord.

MT5 relationship:

TradeRecord.deal
        │
history_deals_get(ticket=<opening deal>)
        │
        ▼
position_id
"""

from backend.trading.lifecycle.trade_record import TradeRecord


class MT5PositionIdentityResolver:
    """
    Resolves the broker position identifier that links every
    deal belonging to the same trade.
    """

    def __init__(self, mt5):
        self.mt5 = mt5

    def resolve(
        self,
        trade_record: TradeRecord,
    ) -> int:

        if not isinstance(
            trade_record,
            TradeRecord,
        ):
            raise TypeError(
                "resolve requires TradeRecord."
            )

        if trade_record.deal is None:
            raise ValueError(
                "TradeRecord has no deal ID."
            )

        deals = self.mt5.history_deals_get(
            ticket=trade_record.deal,
        )

        if deals is None:
            code, message = self.mt5.last_error()

            raise RuntimeError(
                f"history_deals_get failed: "
                f"{code} {message}"
            )

        for deal in deals:

            if deal.ticket != trade_record.deal:
                continue

            position_id = int(
                deal.position_id
            )

            if position_id <= 0:
                raise LookupError(
                    "Matched deal has no valid position ID."
                )

            return position_id

        raise LookupError(
            "No MT5 deal was found for TradeRecord."
        )