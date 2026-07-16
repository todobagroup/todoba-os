"""
TODOBA Position Sizing Mathematics Tests
"""

import pytest

from backend.trading.risk.position_sizing_mathematics import (
    calculate_risk_budget,
    calculate_risk_utilization,
    is_within_tolerance,
)


def test_risk_budget_is_calculated_correctly():
    result = calculate_risk_budget(
        account_equity=5000.0,
        risk_percent=1.0,
    )

    assert result == pytest.approx(
        50.0
    )


def test_risk_utilization_is_calculated_correctly():
    result = calculate_risk_utilization(
        expected_loss_money=45.0,
        risk_budget_money=50.0,
    )

    assert result == pytest.approx(
        0.9
    )


def test_trade_is_approved_within_tolerance():
    approved = is_within_tolerance(
        expected_loss_money=54.0,
        risk_budget_money=50.0,
        tolerance_percent=10.0,
    )

    assert approved is True


def test_trade_is_rejected_over_tolerance():
    approved = is_within_tolerance(
        expected_loss_money=56.0,
        risk_budget_money=50.0,
        tolerance_percent=10.0,
    )

    assert approved is False