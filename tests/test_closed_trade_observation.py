"""
Tests for TODOBA ClosedTradeObservation.
"""

from datetime import datetime, timezone

from backend.trading.lifecycle.closed_trade_observation import (
    ClosedTradeObservation,
)


def test_closed_trade_observation_preserves_broker_evidence():
    closed_at = datetime.now(
        timezone.utc
    )

    observation = ClosedTradeObservation(
        position_id=90001,
        close_deal_id=70002,
        order_id=80002,
        symbol="GOLD.i#",
        action="BUY",
        volume=0.01,
        close_price=4125.0,
        closed_at=closed_at,
        gross_profit=20.0,
        commission=-0.5,
        swap=-0.1,
        fee=0.0,
        net_profit=19.4,
        close_reason="take_profit",
        comment="TODOBA",
    )

    assert observation.position_id == 90001
    assert observation.action == "BUY"
    assert observation.net_profit == 19.4
    assert observation.close_reason == "take_profit"
    assert observation.closed_at == closed_at