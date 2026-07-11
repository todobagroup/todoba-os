"""
TODOBA Trade Lifecycle
"""

from dataclasses import dataclass

from backend.trading.lifecycle.trade_status import TradeStatus


@dataclass
class TradeLifecycle:

    trade_id: str

    status: TradeStatus = TradeStatus.CREATED

    def executing(self):

        self.status = TradeStatus.EXECUTING

    def opened(self):

        self.status = TradeStatus.OPEN

    def closed(self):

        self.status = TradeStatus.CLOSED