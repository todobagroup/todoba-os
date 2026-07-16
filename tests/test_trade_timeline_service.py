"""
TODOBA Trade Timeline Service Tests
"""

import pytest

from backend.trading.lifecycle.trade_timeline_service import (
    TradeTimelineService,
)
from backend.trading.lifecycle.trade_timeline_registry import (
    TradeTimelineRegistry,
)


def create_service():

    registry = TradeTimelineRegistry()

    return TradeTimelineService(
        registry
    )


def test_start_trade_creates_timeline():

    service = create_service()

    timeline = service.start_trade(
        "TRD-001"
    )

    assert timeline.trade_id == "TRD-001"

    assert timeline.event_count == 1

    assert (
        timeline.events[0].stage
        == "trade_opened"
    )


def test_record_appends_event():

    service = create_service()

    service.start_trade(
        "TRD-001"
    )

    service.record(
        "TRD-001",
        stage="signal_received",
        message="BUY GOLD NOW",
    )

    timeline = service.registry.get(
        "TRD-001"
    )

    assert timeline.event_count == 2

    assert (
        timeline.events[1].stage
        == "signal_received"
    )


def test_finish_trade_removes_timeline():

    service = create_service()

    service.start_trade(
        "TRD-001"
    )

    service.finish_trade(
        "TRD-001"
    )

    assert (
        service.registry.get(
            "TRD-001"
        )
        is None
    )


def test_record_unknown_trade_raises():

    service = create_service()

    with pytest.raises(
        LookupError
    ):

        service.record(
            "UNKNOWN",
            stage="signal",
            message="BUY",
        )