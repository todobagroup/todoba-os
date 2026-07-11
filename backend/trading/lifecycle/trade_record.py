
"""
TODOBA Trade Record

Stores basic information about a trade.
"""

from dataclasses import dataclass
from typing import Optional

from backend.trading.lifecycle.trade_status import TradeStatus


@dataclass
class TradeRecord:

    trade_id: str

    symbol: str

    action: str

    volume: float

    status: TradeStatus = TradeStatus.CREATED

    order: Optional[int] = None

    deal: Optional[int] = None