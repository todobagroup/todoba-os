"""
TODOBA Broker State

Represents broker/account facts observed remotely
by a Trusted Execution Agent.

This contract contains facts only.

It does not:

- make trading decisions
- calculate position size
- execute broker orders
- own broker-state transport
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerState:
    """
    Immutable remote broker/account state.
    """

    account_fingerprint: str

    equity: float
    open_position_count: int

    symbol: str

    bid: float
    ask: float
    spread_points: float

    def __post_init__(self) -> None:
        if not self.account_fingerprint:
            raise ValueError(
                "account_fingerprint is required."
            )

        if self.equity <= 0:
            raise ValueError(
                "equity must be greater than zero."
            )

        if self.open_position_count < 0:
            raise ValueError(
                "open_position_count cannot be negative."
            )

        if not self.symbol:
            raise ValueError(
                "symbol is required."
            )