import pytest

from backend.trading.risk.stable_lot_policy import (
    calculate_stable_lot,
)


@pytest.mark.parametrize(
    "equity, expected_volume, cent",
    [
        (100.0, 0.01, True),
        (499.0, 0.01, True),
        (500.0, 0.01, False),
        (999.0, 0.01, False),
        (1000.0, 0.01, False),
        (1499.0, 0.01, False),
        (1500.0, 0.02, False),
        (2499.0, 0.02, False),
        (2500.0, 0.03, False),
        (3499.0, 0.03, False),
        (3500.0, 0.04, False),
        (4499.0, 0.04, False),
        (4500.0, 0.05, False),
        (5499.0, 0.05, False),
        (20000.0, 0.20, False),
        (99000.0, 0.99, False),
        (100000.0, 1.00, False),
    ],
)
def test_stable_lot_policy(
    equity,
    expected_volume,
    cent,
):
    result = calculate_stable_lot(
        equity=equity,
    )

    assert result.approved is True
    assert result.volume == pytest.approx(
        expected_volume
    )
    assert (
        result.cent_account_recommended
        is cent
    )


def test_negative_equity():

    with pytest.raises(
        ValueError,
    ):
        calculate_stable_lot(
            equity=-1,
        )


def test_zero_equity():

    with pytest.raises(
        ValueError,
    ):
        calculate_stable_lot(
            equity=0,
        )


def test_equity_above_supported_limit():

    with pytest.raises(
        ValueError,
    ):
        calculate_stable_lot(
            equity=100001,
        )