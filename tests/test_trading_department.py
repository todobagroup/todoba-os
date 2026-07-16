from pathlib import Path

import pytest

from backend.trading.department.trading_department import (
    TradingDepartment,
)


class DummyMemory:
    pass


class DummyExecutionPipeline:
    pass


def test_trading_department_requires_pipeline():

    with pytest.raises(ValueError):

        TradingDepartment(
            execution_pipeline=None,
            open_trades_storage_path=Path("open_trades.json"),
            memory=DummyMemory(),
        )


def test_trading_department_requires_storage_path():

    with pytest.raises(TypeError):

        TradingDepartment(
            execution_pipeline=DummyExecutionPipeline(),
            open_trades_storage_path="open_trades.json",
            memory=DummyMemory(),
        )