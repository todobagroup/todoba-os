"""
TODOBA Position Sizing Mathematics

Pure mathematical rules used by the
Risk Budget Allocation Engine.
"""


def calculate_risk_budget(
    *,
    account_equity: float,
    risk_percent: float,
) -> float:
    if account_equity <= 0:
        raise ValueError(
            "account_equity must be greater than zero."
        )

    if risk_percent <= 0:
        raise ValueError(
            "risk_percent must be greater than zero."
        )

    return account_equity * (
        risk_percent / 100.0
    )


def calculate_risk_utilization(
    *,
    expected_loss_money: float,
    risk_budget_money: float,
) -> float:
    if expected_loss_money < 0:
        raise ValueError(
            "expected_loss_money cannot be negative."
        )

    if risk_budget_money <= 0:
        raise ValueError(
            "risk_budget_money must be greater than zero."
        )

    return (
        expected_loss_money
        / risk_budget_money
    )


def is_within_tolerance(
    *,
    expected_loss_money: float,
    risk_budget_money: float,
    tolerance_percent: float,
) -> bool:
    if tolerance_percent < 0:
        raise ValueError(
            "tolerance_percent cannot be negative."
        )

    maximum_allowed_loss = (
        risk_budget_money
        * (1.0 + tolerance_percent / 100.0)
    )

    return (
        expected_loss_money
        <= maximum_allowed_loss
    )