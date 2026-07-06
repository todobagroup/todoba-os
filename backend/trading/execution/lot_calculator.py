"""
TODOBA Lot Calculator

Calculates lot size based on a selected policy.
"""


def calculate(policy_name: str) -> float:
    """
    Placeholder implementation.

    Real calculation policies
    will be added in future versions.
    """

    if policy_name == "FIXED_001":
        return 0.01

    raise ValueError(f"Unknown lot policy: {policy_name}")