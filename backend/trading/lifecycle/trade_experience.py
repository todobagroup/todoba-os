"""
TODOBA Trade Experience
"""

from dataclasses import dataclass


@dataclass
class TradeExperience:

    trade_id: str

    outcome: str

    reason: str