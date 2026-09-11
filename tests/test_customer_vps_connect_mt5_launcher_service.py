from pathlib import Path

import pytest

from backend.commercial.customer_vps_connect_mt5_launcher_service import (
    CustomerVPSConnectMT5LauncherService,
)


TERMINAL = r"C:\MT5\terminal64.exe"
CONFIG = r"C:\TODOBA\TODOBA_VPS_Startup.ini"


class FakeProcessLauncher:
    def __init__(
        self,
    ):
        self.calls = []

    def launch(
        self,
        *,
        executable,
        arguments,
    ):
        self.calls.append(
            (
                executable,
                tuple(arguments),
            )
        )

        return 4321


def test_launches_exact_terminal_with_exact_config_argument():
    process_launcher = FakeProcessLauncher()

    service = (
        CustomerVPSConnectMT5LauncherService(
            process_launcher=process_launcher,
        )
    )

    result = service.launch(
        terminal_path=TERMINAL,
        config_path=CONFIG,
    )

    assert process_launcher.calls == [
        (
            TERMINAL,
            (
                f"/config:{CONFIG}",
            ),
        )
    ]

    assert result.process_id == 4321
    assert result.terminal_path == TERMINAL
    assert result.config_path == CONFIG


@pytest.mark.parametrize(
    "terminal_path",
    [
        "",
        "   ",
        r"C:\MT5\terminal.exe",
        r"C:\MT5\metaeditor64.exe",
    ],
)
def test_rejects_invalid_terminal_path(
    terminal_path,
):
    service = (
        CustomerVPSConnectMT5LauncherService(
            process_launcher=FakeProcessLauncher(),
        )
    )

    with pytest.raises(
        ValueError,
    ):
        service.launch(
            terminal_path=terminal_path,
            config_path=CONFIG,
        )


@pytest.mark.parametrize(
    "config_path",
    [
        "",
        "   ",
        r"C:\TODOBA\startup.txt",
        "C:\\TODOBA\\bad.ini\n/portable",
    ],
)
def test_rejects_invalid_config_path(
    config_path,
):
    service = (
        CustomerVPSConnectMT5LauncherService(
            process_launcher=FakeProcessLauncher(),
        )
    )

    with pytest.raises(
        ValueError,
    ):
        service.launch(
            terminal_path=TERMINAL,
            config_path=config_path,
        )


def test_launcher_owner_has_no_account_or_shutdown_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_mt5_launcher_service.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "login(",
        "password",
        "MetaTrader5",
        "purchase",
        "migrate",
        "terminate(",
        "kill(",
        "shell=True",
        "os.system",
    ):
        assert forbidden not in source
