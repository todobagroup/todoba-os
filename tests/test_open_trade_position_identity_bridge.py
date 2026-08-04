from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)

from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)

from backend.trading.lifecycle.mt5_position_identity_resolver import (
    MT5PositionIdentityResolver,
)

from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)


class FakeDeal:

    def __init__(
        self,
        *,
        ticket,
        position_id,
    ):
        self.ticket = ticket
        self.position_id = position_id


class FakeMT5:

    def __init__(self):
        self.DEAL = FakeDeal(
            ticket=789012,
            position_id=555001,
        )

    def history_deals_get(
        self,
        ticket,
    ):
        return [
            self.DEAL
        ]

    def last_error(self):
        return (
            0,
            "OK",
        )


def test_trade_record_resolves_position_and_registers_open_trade():

    trade_record = TradeRecord(
        trade_id="proof055-001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=123456,
        deal=789012,
    )

    resolver = MT5PositionIdentityResolver(
        FakeMT5()
    )

    position_id = resolver.resolve(
        trade_record
    )

    assert position_id == 555001


    registry = OpenTradeRegistry()

    tracked_trade = registry.register(
        trade_record=trade_record,
        position_id=position_id,
    )

    assert tracked_trade.position_id == (
        555001
    )

    assert registry.size() == 1

    stored = registry.get(
        "proof055-001"
    )

    assert stored is not None

    assert stored.trade_record == (
        trade_record
    )