"""
TODOBA Trade Timeline Tests
"""

import pytest

from backend.trading.lifecycle.trade_timeline import (
    TradeTimeline,
)
from backend.trading.lifecycle.trade_timeline_event import (
    TradeTimelineEvent,
)


def test_append_event():

    timeline = TradeTimeline(
        "TRD-000001"
    )

    event = TradeTimelineEvent(
        trade_id="TRD-000001",
        stage="signal_received",
        message="BUY GOLD NOW",
    )

    timeline.append(event)

    assert timeline.event_count == 1

    assert timeline.events[0] == event


def test_timeline_preserves_order():

    timeline = TradeTimeline(
        "TRD-000001"
    )

    timeline.append(
        TradeTimelineEvent(
            trade_id="TRD-000001",
            stage="signal",
            message="Signal",
        )
    )

    timeline.append(
        TradeTimelineEvent(
            trade_id="TRD-000001",
            stage="execution",
            message="Executed",
        )
    )

    assert (
        timeline.events[0].stage
        == "signal"
    )

    assert (
        timeline.events[1].stage
        == "execution"
    )


def test_event_from_other_trade_is_rejected():

    timeline = TradeTimeline(
        "TRD-000001"
    )

    with pytest.raises(
        ValueError
    ):

        timeline.append(
            TradeTimelineEvent(
                trade_id="TRD-000999",
                stage="execution",
                message="Wrong trade",
            )
        )