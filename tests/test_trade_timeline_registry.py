"""
TODOBA Trade Timeline Registry Tests
"""

from backend.trading.lifecycle.trade_timeline_registry import (
    TradeTimelineRegistry,
)


def test_create_and_get_timeline():

    registry = TradeTimelineRegistry()

    timeline = registry.create(
        "TRD-001"
    )

    assert registry.get(
        "TRD-001"
    ) is timeline


def test_remove_timeline():

    registry = TradeTimelineRegistry()

    registry.create(
        "TRD-001"
    )

    registry.remove(
        "TRD-001"
    )

    assert (
        registry.get("TRD-001")
        is None
    )