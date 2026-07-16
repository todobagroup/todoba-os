"""
TODOBA Trade Timeline Service

Coordinates trade timelines.

The service owns timeline creation and
event recording.

It does not know MT5, Telegram,
or Trading Runtime.
"""

from backend.trading.lifecycle.trade_timeline import (
    TradeTimeline,
)
from backend.trading.lifecycle.trade_timeline_event import (
    TradeTimelineEvent,
)
from backend.trading.lifecycle.trade_timeline_registry import (
    TradeTimelineRegistry,
)


class TradeTimelineService:
    """
    Coordinates timelines for all trades.
    """

    def __init__(
        self,
        registry: TradeTimelineRegistry,
    ):

        if not isinstance(
            registry,
            TradeTimelineRegistry,
        ):
            raise TypeError(
                "TradeTimelineService requires "
                "TradeTimelineRegistry."
            )

        self.registry = registry

    def start_trade(
        self,
        trade_id: str,
    ) -> TradeTimeline:
        """
        Create a timeline for a newly
        opened trade.
        """

        timeline = self.registry.create(
            trade_id
        )

        timeline.append(
            TradeTimelineEvent(
                trade_id=trade_id,
                stage="trade_opened",
                message="Trade opened.",
            )
        )

        return timeline

    def record(
        self,
        trade_id: str,
        *,
        stage: str,
        message: str,
        context: dict | None = None,
    ) -> None:
        """
        Append one event to a trade timeline.
        """

        timeline = self.registry.get(
            trade_id
        )

        if timeline is None:
            raise LookupError(
                f"Unknown trade: {trade_id}"
            )

        timeline.append(
            TradeTimelineEvent(
                trade_id=trade_id,
                stage=stage,
                message=message,
                context=context or {},
            )
        )

    def finish_trade(
        self,
        trade_id: str,
    ) -> None:
        """
        Remove the timeline after the
        trade lifecycle has completed.
        """

        self.registry.remove(
            trade_id
        )