"""
Tests for TODOBA MT5 connection recovery.
"""

from backend.trading.broker.mt5_client import (
    MT5Client,
)


class FakeMT5:
    def __init__(
        self,
        *,
        initialize_results,
    ):
        self.initialize_results = list(
            initialize_results
        )
        self.initialize_calls = 0
        self.shutdown_calls = 0
        self.connected = False

    def initialize(self):
        self.initialize_calls += 1

        result = self.initialize_results.pop(0)

        self.connected = result

        return result

    def shutdown(self):
        self.shutdown_calls += 1
        self.connected = False

    def terminal_info(self):
        if self.connected:
            return object()

        return None


def test_reconnect_succeeds_after_temporary_failure():
    fake_mt5 = FakeMT5(
        initialize_results=[
            False,
            False,
            True,
        ]
    )

    client = MT5Client(
        mt5_module=fake_mt5
    )

    connected = client.reconnect(
        max_attempts=3
    )

    assert connected is True
    assert fake_mt5.initialize_calls == 3
    assert client.is_connected() is True


def test_reconnect_returns_false_after_all_attempts():
    fake_mt5 = FakeMT5(
        initialize_results=[
            False,
            False,
            False,
        ]
    )

    client = MT5Client(
        mt5_module=fake_mt5
    )

    connected = client.reconnect(
        max_attempts=3
    )

    assert connected is False
    assert fake_mt5.initialize_calls == 3
    assert client.is_connected() is False