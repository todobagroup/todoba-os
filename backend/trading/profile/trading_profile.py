"""
TODOBA Trading Profile

Defines how a trading customer/profile is allowed to trade.

Version: 1.0
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingProfile:
    """
    Immutable trading profile.

    A profile describes trading rules.
    It does not store broker login, password, token, or API keys.
    """

    profile_name: str
    risk_percent: float
    max_open_trades: int
    allowed_symbols: tuple[str, ...]
    lot_policy_name: str