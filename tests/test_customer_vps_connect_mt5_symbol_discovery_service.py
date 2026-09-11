from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)

from backend.commercial.customer_vps_connect_mt5_symbol_discovery_service import (
    CustomerVPSConnectMT5SymbolDiscoveryService,
)


TERMINAL = r"C:\MT5\terminal64.exe"
INSTALLATION = r"C:\MT5"
DATA = (
    "C:\\Users\\Customer\\AppData\\Roaming\\"
    "MetaQuotes\\Terminal\\ABC"
)
LOGIN = 12345678
SERVER = "Broker-Pro"
FINGERPRINT = f"{SERVER}:{LOGIN}"


def _preflight():
    return CustomerMT5SetupPreflightResult(
        terminal_path=TERMINAL,
        installation_path=INSTALLATION,
        data_path=DATA,
        portable=False,
        login=LOGIN,
        server=SERVER,
        margin_mode=2,
        account_fingerprint=FINGERPRINT,
    )


class FakeMT5:
    ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 2

    def __init__(
        self,
        *,
        login=LOGIN,
        server=SERVER,
        terminal_path=INSTALLATION,
        data_path=DATA,
        symbols=("EURUSD", "XAUUSD.a", "GOLD"),
    ):
        self.login = login
        self.server = server
        self.terminal_path = terminal_path
        self.data_path = data_path
        self.symbols = symbols

        self.initialize_calls = []
        self.shutdown_calls = 0

    def initialize(
        self,
        path,
        *,
        portable,
    ):
        self.initialize_calls.append(
            (
                path,
                portable,
            )
        )
        return True

    def shutdown(
        self,
    ):
        self.shutdown_calls += 1

    def terminal_info(
        self,
    ):
        return SimpleNamespace(
            path=self.terminal_path,
            data_path=self.data_path,
        )

    def account_info(
        self,
    ):
        return SimpleNamespace(
            login=self.login,
            server=self.server,
            margin_mode=2,
        )

    def symbols_get(
        self,
    ):
        return tuple(
            SimpleNamespace(
                name=name,
            )
            for name in self.symbols
        )


def test_discovers_symbols_only_from_exact_bound_mt5():
    mt5 = FakeMT5()

    service = (
        CustomerVPSConnectMT5SymbolDiscoveryService(
            mt5_module=mt5,
        )
    )

    symbols = service.discover(
        preflight_result=_preflight(),
    )

    assert symbols == (
        "EURUSD",
        "XAUUSD.a",
        "GOLD",
    )

    assert mt5.initialize_calls == [
        (
            TERMINAL,
            False,
        )
    ]

    assert mt5.shutdown_calls == 1


def test_symbol_discovery_fails_closed_if_account_changed():
    mt5 = FakeMT5(
        login=99999999,
    )

    service = (
        CustomerVPSConnectMT5SymbolDiscoveryService(
            mt5_module=mt5,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="account",
    ):
        service.discover(
            preflight_result=_preflight(),
        )

    assert mt5.shutdown_calls == 1


def test_symbol_discovery_fails_closed_if_terminal_changed():
    mt5 = FakeMT5(
        terminal_path=r"C:\OtherMT5",
    )

    service = (
        CustomerVPSConnectMT5SymbolDiscoveryService(
            mt5_module=mt5,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="terminal",
    ):
        service.discover(
            preflight_result=_preflight(),
        )

    assert mt5.shutdown_calls == 1


def test_symbol_discovery_fails_closed_without_symbols():
    mt5 = FakeMT5(
        symbols=(),
    )

    service = (
        CustomerVPSConnectMT5SymbolDiscoveryService(
            mt5_module=mt5,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="symbol",
    ):
        service.discover(
            preflight_result=_preflight(),
        )

    assert mt5.shutdown_calls == 1


def test_symbol_discovery_owner_is_read_only():
    source = (
        Path(
            "backend/commercial/"
            "customer_vps_connect_mt5_symbol_discovery_service.py"
        )
        .read_text(
            encoding="utf-8-sig"
        )
    )

    for forbidden in (
        "login(",
        "password",
        "order_send",
        "trade",
        "purchase",
        "migrate",
        "common.ini",
        "WebRequestUrl",
        "write_text",
        "write_bytes",
        "subprocess",
        "Popen",
        "terminate(",
        "kill(",
    ):
        assert forbidden not in source
