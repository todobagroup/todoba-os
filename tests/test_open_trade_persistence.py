"""
Tests for TODOBA OpenTradePersistence.
"""

from pathlib import Path
from types import SimpleNamespace

from backend.trading.lifecycle.mt5_position_identity_resolver import (
    MT5PositionIdentityResolver,
)
from backend.trading.lifecycle.open_trade_persistence import (
    OpenTradePersistence,
)
from backend.trading.lifecycle.open_trade_registry import (
    OpenTradeRegistry,
)
from backend.trading.lifecycle.open_trade_repository import (
    OpenTradeRepository,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)
from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)


class FakeMT5:

    def history_deals_get(
        self,
        ticket,
    ):

        return [
            SimpleNamespace(
                ticket=ticket,
                position_id=987654,
            )
        ]


def test_trade_is_registered_and_persisted(
    tmp_path: Path,
):

    registry = OpenTradeRegistry()

    repository = OpenTradeRepository(
        tmp_path / "open_trades.json"
    )

    resolver = MT5PositionIdentityResolver(
        FakeMT5()
    )

    persistence = OpenTradePersistence(
        registry=registry,
        repository=repository,
        position_resolver=resolver,
    )

    trade_record = TradeRecord(
        trade_id="TRD-TEST-000001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=111,
        deal=222,
    )

    tracked_trade = persistence.persist(
        trade_record
    )

    assert tracked_trade.trade_record.trade_id == (
        "TRD-TEST-000001"
    )

    assert tracked_trade.position_id == 987654

    restored = repository.load()

    assert len(restored) == 1

    assert (
        restored[0].trade_record.trade_id
        == "TRD-TEST-000001"
    )

    assert restored[0].position_id == 987654