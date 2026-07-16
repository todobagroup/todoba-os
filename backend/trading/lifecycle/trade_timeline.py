"""
TODOBA Trade Timeline

Maintains an ordered timeline for one trade.
"""

from backend.trading.lifecycle.trade_timeline_event import (
    TradeTimelineEvent,
)


class TradeTimeline:
    """
    Timeline of one trade.
    """

    def __init__(
        self,
        trade_id: str,
    ):

        self.trade_id = trade_id

        self._events: list[
            TradeTimelineEvent
        ] = []

    def append(
        self,
        event: TradeTimelineEvent,
    ) -> None:

        if event.trade_id != self.trade_id:
            raise ValueError(
                "Timeline event belongs to "
                "another trade."
            )

        self._events.append(event)

    @property
    def events(
        self,
    ) -> tuple[
        TradeTimelineEvent,
        ...
    ]:

        return tuple(
            self._events
        )

    @property
    def event_count(
        self,
    ) -> int:

        return len(
            self._events
        )