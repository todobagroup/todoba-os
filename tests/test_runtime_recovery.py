"""
Tests for TODOBA RuntimeRecovery.
"""

from pathlib import Path

import pytest

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
from backend.trading.runtime.runtime_recovery import (
    RuntimeRecovery,
)


def create_trade():

    return TradeRecord(
        trade_id="TRD-000001",
        symbol="XAUUSD",
        action="BUY",
        volume=0.01,
        status=TradeStatus.OPEN,
        order=1001,
        deal=2001,
    )


def prepare_repository(
    tmp_path: Path,
):

    repository = OpenTradeRepository(
        tmp_path / "open_trades.json"
    )

    registry = OpenTradeRegistry()

    tracked = registry.register(
        trade_record=create_trade(),
        position_id=3001,
        context={
            "strategy": "London Breakout",
        },
    )

    repository.save(
        [tracked]
    )

    return repository


def test_runtime_restores_registry(
    tmp_path: Path,
):

    repository = prepare_repository(
        tmp_path
    )

    registry = OpenTradeRegistry()

    recovery = RuntimeRecovery(
        repository=repository,
        registry=registry,
    )

    restored = recovery.restore()

    assert restored == 1

    tracked = registry.list()[0]

    assert (
        tracked.trade_record.trade_id
        == "TRD-000001"
    )

    assert tracked.position_id == 3001


def test_runtime_restore_empty_repository(
    tmp_path: Path,
):

    repository = OpenTradeRepository(
        tmp_path / "missing.json"
    )

    registry = OpenTradeRegistry()

    recovery = RuntimeRecovery(
        repository=repository,
        registry=registry,
    )

    assert recovery.restore() == 0

    assert registry.list() == []


def test_runtime_requires_repository():

    with pytest.raises(
        TypeError,
        match="OpenTradeRepository",
    ):

        RuntimeRecovery(
            repository=None,
            registry=OpenTradeRegistry(),
        )


def test_runtime_requires_registry(
    tmp_path: Path,
):

    repository = OpenTradeRepository(
        tmp_path / "open_trades.json"
    )

    with pytest.raises(
        TypeError,
        match="OpenTradeRegistry",
    ):

        RuntimeRecovery(
            repository=repository,
            registry=None,
        )