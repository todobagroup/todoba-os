"""
TODOBA MT5 Trade History Reader

Reads broker evidence for closed MT5 positions and converts
the evidence into ClosedTradeObservation.

This reader does not:
- decide whether a trade was good or bad;
- create TradeExperience;
- write to Brain Memory.
"""

from datetime import datetime, timezone
from typing import Optional

import MetaTrader5 as mt5

from backend.trading.lifecycle.closed_trade_observation import (
    ClosedTradeObservation,
)


class MT5TradeHistoryReader:
    """
    Read closed-position evidence from MT5 deal history.
    """

    def __init__(self, mt5_module=mt5):
        self.mt5 = mt5_module

    def read_closed_position(
        self,
        position_id: int,
    ) -> Optional[ClosedTradeObservation]:
        """
        Return the most recent closing deal for one position.

        Returns None when the position has no closing deal yet.
        """

        if not isinstance(position_id, int):
            raise TypeError(
                "position_id must be an integer."
            )

        if position_id <= 0:
            raise ValueError(
                "position_id must be greater than zero."
            )

        deals = self.mt5.history_deals_get(
            position=position_id
        )

        if deals is None:
            last_error = self._read_last_error()

            raise RuntimeError(
                "MT5 history_deals_get failed for "
                f"position {position_id}: {last_error}"
            )

        closing_deals = [
            deal
            for deal in deals
            if self._is_closing_deal(deal)
        ]

        if not closing_deals:
            return None

        close_deal = max(
            closing_deals,
            key=lambda deal: (
                getattr(deal, "time_msc", 0),
                getattr(deal, "time", 0),
                getattr(deal, "ticket", 0),
            ),
        )

        gross_profit = float(
            getattr(close_deal, "profit", 0.0)
        )

        commission = float(
            getattr(close_deal, "commission", 0.0)
        )

        swap = float(
            getattr(close_deal, "swap", 0.0)
        )

        fee = float(
            getattr(close_deal, "fee", 0.0)
        )

        net_profit = (
            gross_profit
            + commission
            + swap
            + fee
        )

        return ClosedTradeObservation(
            position_id=position_id,
            close_deal_id=int(
                getattr(close_deal, "ticket")
            ),
            order_id=self._optional_int(
                getattr(
                    close_deal,
                    "order",
                    None,
                )
            ),
            symbol=str(
                getattr(close_deal, "symbol", "")
            ),
            action=self._resolve_action(
                close_deal
            ),
            volume=float(
                getattr(close_deal, "volume", 0.0)
            ),
            close_price=float(
                getattr(close_deal, "price", 0.0)
            ),
            closed_at=self._to_utc_datetime(
                getattr(close_deal, "time", 0)
            ),
            gross_profit=gross_profit,
            commission=commission,
            swap=swap,
            fee=fee,
            net_profit=net_profit,
            close_reason=self._resolve_reason(
                close_deal
            ),
            comment=str(
                getattr(close_deal, "comment", "")
            ),
        )

    def _is_closing_deal(self, deal) -> bool:
        entry = getattr(
            deal,
            "entry",
            None,
        )

        closing_entries = {
            self.mt5.DEAL_ENTRY_OUT,
            self.mt5.DEAL_ENTRY_OUT_BY,
            self.mt5.DEAL_ENTRY_INOUT,
        }

        return entry in closing_entries

    def _resolve_action(self, deal) -> str:
        """
        Infer the original position action from the closing deal.
        """

        deal_type = getattr(
            deal,
            "type",
            None,
        )

        if deal_type == self.mt5.DEAL_TYPE_SELL:
            return "BUY"

        if deal_type == self.mt5.DEAL_TYPE_BUY:
            return "SELL"

        return "UNKNOWN"

    def _resolve_reason(self, deal) -> str:
        reason = getattr(
            deal,
            "reason",
            None,
        )

        reason_map = {
            self.mt5.DEAL_REASON_TP: "take_profit",
            self.mt5.DEAL_REASON_SL: "stop_loss",
            self.mt5.DEAL_REASON_SO: "stop_out",
            self.mt5.DEAL_REASON_CLIENT: "manual_desktop",
            self.mt5.DEAL_REASON_MOBILE: "manual_mobile",
            self.mt5.DEAL_REASON_WEB: "manual_web",
            self.mt5.DEAL_REASON_EXPERT: "expert",
        }

        return reason_map.get(
            reason,
            "unknown",
        )

    def _to_utc_datetime(
        self,
        timestamp: int,
    ) -> datetime:
        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )

    def _optional_int(
        self,
        value,
    ) -> Optional[int]:
        if value in (None, 0):
            return None

        return int(value)

    def _read_last_error(self):
        last_error = getattr(
            self.mt5,
            "last_error",
            None,
        )

        if callable(last_error):
            return last_error()

        return "unknown"
