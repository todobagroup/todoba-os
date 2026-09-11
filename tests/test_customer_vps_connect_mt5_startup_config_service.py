from pathlib import Path

import pytest

from backend.commercial.customer_vps_connect_mt5_startup_config_service import (
    CustomerVPSConnectMT5StartupConfigService,
)


CONFIG_TEXT = (
    "[StartUp]\n"
    "Expert=TODOBA_Trusted_Agent\n"
    "Symbol=XAUUSD.a\n"
    "Period=H1\n"
)


def test_writes_dedicated_todoba_startup_config(tmp_path):
    service = (
        CustomerVPSConnectMT5StartupConfigService()
    )

    result = service.write(
        directory=tmp_path,
        config_text=CONFIG_TEXT,
    )

    expected = (
        tmp_path
        / "TODOBA_VPS_Startup.ini"
    )

    assert result.config_path == str(
        expected.resolve()
    )

    assert expected.read_text(
        encoding="utf-8"
    ) == CONFIG_TEXT


def test_same_config_is_idempotent(tmp_path):
    service = (
        CustomerVPSConnectMT5StartupConfigService()
    )

    first = service.write(
        directory=tmp_path,
        config_text=CONFIG_TEXT,
    )

    second = service.write(
        directory=tmp_path,
        config_text=CONFIG_TEXT,
    )

    assert first.config_path == second.config_path
    assert second.already_present is True


def test_conflicting_existing_config_fails_closed(tmp_path):
    target = (
        tmp_path
        / "TODOBA_VPS_Startup.ini"
    )

    target.write_text(
        "[StartUp]\nSymbol=EURUSD\n",
        encoding="utf-8",
    )

    service = (
        CustomerVPSConnectMT5StartupConfigService()
    )

    with pytest.raises(
        FileExistsError,
        match="config",
    ):
        service.write(
            directory=tmp_path,
            config_text=CONFIG_TEXT,
        )


@pytest.mark.parametrize(
    "config_text",
    [
        "",
        "   ",
        "[Common]\nPassword=secret\n",
        "[StartUp]\nLogin=123\n",
        "[StartUp]\nAllowLiveTrading=1\n",
    ],
)
def test_rejects_empty_or_authority_bearing_config(
    tmp_path,
    config_text,
):
    service = (
        CustomerVPSConnectMT5StartupConfigService()
    )

    with pytest.raises(
        ValueError,
    ):
        service.write(
            directory=tmp_path,
            config_text=config_text,
        )


def test_startup_config_owner_has_no_process_or_account_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_mt5_startup_config_service.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "subprocess",
        "Popen",
        "Start-Process",
        "login(",
        "password",
        "MetaTrader5",
        "purchase",
        "migrate",
        "terminate(",
        "kill(",
    ):
        assert forbidden not in source


def test_creates_dedicated_startup_directory_on_fresh_customer(
    tmp_path,
):
    service = (
        CustomerVPSConnectMT5StartupConfigService()
    )

    directory = (
        tmp_path
        / "TODOBA"
        / "VPS Connect"
    )

    assert not directory.exists()

    result = service.write(
        directory=directory,
        config_text=CONFIG_TEXT,
    )

    assert directory.is_dir()

    target = (
        directory
        / "TODOBA_VPS_Startup.ini"
    )

    assert target.is_file()

    assert result.config_path == str(
        target.resolve()
    )


