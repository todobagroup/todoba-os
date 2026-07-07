"""
TODOBA Account Information

Represents a trading account.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountInfo:

    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: int