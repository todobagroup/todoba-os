"""
TODOBA Open Trade Registry

Keeps track of open trades that TODOBA must monitor.

The registry stores organizational trade identity together
with the official MT5 position identity.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from backend.trading.lifecycle.trade_record import TradeRecord
from backend.trading.lifecycle.trade_status import TradeStatus


@dataclass
class TrackedTrade:
    """
    One open trade registered for lifecycle monitoring.
    """

    trade_record: TradeRecord
    position_id: int
    context: dict[str, Any] = field(
        default_factory=dict
    )


class OpenTradeRegistry:
    """
    In-memory registry of trades currently being monitored.
    """

    def __init__(self):
        self._trades: dict[str, TrackedTrade] = {}

    def register(
        self,
        *,
        trade_record: TradeRecord,
        position_id: int,
        context: Optional[dict] = None,
    ) -> TrackedTrade:
        if not isinstance(
            trade_record,
            TradeRecord,
        ):
            raise TypeError(
                "OpenTradeRegistry requires TradeRecord."
            )

        if trade_record.status != TradeStatus.OPEN:
            raise ValueError(
                "Only OPEN TradeRecord can be registered."
            )

        if not isinstance(position_id, int):
            raise TypeError(
                "position_id must be an integer."
            )

        if position_id <= 0:
            raise ValueError(
                "position_id must be greater than zero."
            )

        if trade_record.trade_id in self._trades:
            raise ValueError(
                f"Trade already registered: "
                f"{trade_record.trade_id}"
            )

        tracked_trade = TrackedTrade(
            trade_record=trade_record,
            position_id=position_id,
            context=dict(context or {}),
        )

        self._trades[
            trade_record.trade_id
        ] = tracked_trade

        return tracked_trade

    def get(
        self,
        trade_id: str,
    ) -> Optional[TrackedTrade]:
        return self._trades.get(
            trade_id
        )

    def remove(
        self,
        trade_id: str,
    ) -> Optional[TrackedTrade]:
        return self._trades.pop(
            trade_id,
            None,
        )

    def list(
        self,
    ) -> list[TrackedTrade]:
        return list(
            self._trades.values()
        )

    def size(self) -> int:
        return len(
            self._trades
        )