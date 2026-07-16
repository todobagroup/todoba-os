"""
TODOBA Trade Timeline Registry
"""

from backend.trading.lifecycle.trade_timeline import (
    TradeTimeline,
)


class TradeTimelineRegistry:

    def __init__(self):

        self._timelines = {}

    def create(
        self,
        trade_id: str,
    ) -> TradeTimeline:

        timeline = TradeTimeline(
            trade_id
        )

        self._timelines[
            trade_id
        ] = timeline

        return timeline

    def get(
        self,
        trade_id: str,
    ):

        return self._timelines.get(
            trade_id
        )

    def remove(
        self,
        trade_id: str,
    ):

        self._timelines.pop(
            trade_id,
            None,
        )