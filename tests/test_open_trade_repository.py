"""
Tests for TODOBA OpenTradeRepository.
"""

from pathlib import Path

import pytest

from backend.trading.lifecycle.open_trade_registry import (
    TrackedTrade,
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


def create_tracked_trade():

    trade = TradeRecord(
        trade_id="TRD-000001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=1001,
        deal=2001,
    )

    return TrackedTrade(
        trade_record=trade,
        position_id=3001,
        context={
            "strategy": "London Breakout",
        },
    )


def test_repository_saves_and_loads_trades(
    tmp_path: Path,
):

    repository = OpenTradeRepository(
        tmp_path / "open_trades.json"
    )

    tracked = create_tracked_trade()

    repository.save(
        [tracked]
    )

    restored = repository.load()

    assert len(restored) == 1

    loaded = restored[0]

    assert (
        loaded.trade_record.trade_id
        == "TRD-000001"
    )

    assert loaded.position_id == 3001

    assert (
        loaded.context["strategy"]
        == "London Breakout"
    )


def test_repository_returns_empty_when_missing(
    tmp_path: Path,
):

    repository = OpenTradeRepository(
        tmp_path / "missing.json"
    )

    assert repository.load() == []


def test_repository_clear_removes_storage(
    tmp_path: Path,
):

    repository = OpenTradeRepository(
        tmp_path / "open_trades.json"
    )

    repository.save(
        [create_tracked_trade()]
    )

    assert repository.exists()

    repository.clear()

    assert not repository.exists()


def test_repository_requires_path():

    with pytest.raises(
        TypeError,
        match="storage_path",
    ):

        OpenTradeRepository(
            "not-a-path"
        )