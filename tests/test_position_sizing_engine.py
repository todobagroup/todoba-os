"""
TODOBA Stable Position Sizing Engine Tests
"""

import pytest

from backend.trading.risk.position_sizing_engine import (
    PositionSizingEngine,
)


@pytest.mark.parametrize(
    "equity, expected_volume",
    [
        (100.0, 0.01),
        (500.0, 0.01),
        (1000.0, 0.01),
        (1500.0, 0.02),
        (5000.0, 0.05),
    ],
)
def test_stable_position_sizing(
    equity,
    expected_volume,
):
    engine = PositionSizingEngine()

    result = engine.evaluate(
        account_equity=equity,
    )

    assert result.approved is True
    assert result.volume == pytest.approx(
        expected_volume
    )


def test_stable_position_sizing_rejects_invalid_equity():
    engine = PositionSizingEngine()

    with pytest.raises(ValueError):
        engine.evaluate(
            account_equity=0,
        )