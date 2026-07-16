"""
TODOBA MT5 Connection Monitor

Checks MT5 connection health and attempts recovery.
"""

from dataclasses import dataclass

from backend.trading.broker.mt5_client import (
    MT5Client,
)


@dataclass(frozen=True)
class MT5ConnectionStatus:
    connected: bool
    recovered: bool
    attempts: int


class MT5ConnectionMonitor:

    def __init__(
        self,
        *,
        client: MT5Client,
        max_reconnect_attempts: int = 3,
        reconnect_delay_seconds: float = 0.0,
    ):
        if not isinstance(
            client,
            MT5Client,
        ):
            raise TypeError(
                "MT5ConnectionMonitor requires MT5Client."
            )

        if max_reconnect_attempts <= 0:
            raise ValueError(
                "max_reconnect_attempts must be greater than zero."
            )

        if reconnect_delay_seconds < 0:
            raise ValueError(
                "reconnect_delay_seconds cannot be negative."
            )

        self.client = client
        self.max_reconnect_attempts = (
            max_reconnect_attempts
        )
        self.reconnect_delay_seconds = (
            reconnect_delay_seconds
        )

    def check(self) -> MT5ConnectionStatus:
        if self.client.is_connected():
            return MT5ConnectionStatus(
                connected=True,
                recovered=False,
                attempts=0,
            )

        connected = self.client.reconnect(
            max_attempts=(
                self.max_reconnect_attempts
            ),
            delay_seconds=(
                self.reconnect_delay_seconds
            ),
        )

        return MT5ConnectionStatus(
            connected=connected,
            recovered=connected,
            attempts=(
                self.max_reconnect_attempts
            ),
        )