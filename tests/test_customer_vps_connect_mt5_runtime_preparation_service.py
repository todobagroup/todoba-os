from pathlib import Path

import pytest

from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallationResult,
)

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)

from backend.commercial.customer_vps_connect_mt5_runtime_preparation_service import (
    CustomerVPSConnectMT5RuntimePreparationService,
)


TERMINAL = r"C:\MT5\terminal64.exe"
DATA = r"C:\Users\Customer\AppData\Roaming\MetaQuotes\Terminal\ABC"
FINGERPRINT = "Broker-Pro:12345678"
EX5 = DATA + r"\MQL5\Experts\TODOBA_Trusted_Agent.ex5"
SHA256 = "a" * 64


def _preflight(
    *,
    terminal_path=TERMINAL,
    data_path=DATA,
    fingerprint=FINGERPRINT,
):
    return CustomerMT5SetupPreflightResult(
        terminal_path=terminal_path,
        installation_path=str(
            Path(terminal_path).parent
        ),
        data_path=data_path,
        portable=False,
        login=12345678,
        server="Broker-Pro",
        margin_mode=2,
        account_fingerprint=fingerprint,
    )


def _installation(
    *,
    terminal_path=TERMINAL,
    data_path=DATA,
    fingerprint=FINGERPRINT,
):
    return CustomerMT5EX5InstallationResult(
        terminal_path=terminal_path,
        data_path=data_path,
        account_fingerprint=fingerprint,
        installed_path=EX5,
        artifact_sha256=SHA256,
        artifact_size_bytes=1024,
        already_present=True,
    )


def test_prepare_accepts_only_same_authoritative_mt5_identity():
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    result = service.prepare(
        preflight_result=_preflight(),
        installation_result=_installation(),
    )

    assert result.terminal_path == TERMINAL
    assert result.data_path == DATA
    assert result.account_fingerprint == FINGERPRINT
    assert result.installed_path == EX5


@pytest.mark.parametrize(
    "installation",
    [
        _installation(
            terminal_path=r"C:\Other\terminal64.exe"
        ),
        _installation(
            data_path=r"C:\Other\Data"
        ),
        _installation(
            fingerprint="Broker-Pro:99999999"
        ),
    ],
)
def test_prepare_fails_closed_on_cross_mt5_identity(
    installation,
):
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        service.prepare(
            preflight_result=_preflight(),
            installation_result=installation,
        )



def test_build_startup_plan_is_bound_to_verified_runtime():
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    bound = service.prepare(
        preflight_result=_preflight(),
        installation_result=_installation(),
    )

    plan = service.build_startup_plan(
        preparation_result=bound,
        symbol="GOLD.a",
    )

    assert plan.terminal_path == TERMINAL
    assert plan.data_path == DATA
    assert plan.account_fingerprint == FINGERPRINT
    assert plan.expert_name == "TODOBA_Trusted_Agent"
    assert plan.symbol == "GOLD.a"
    assert plan.period == "H1"


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        "   ",
        "\n",
        "EURUSD\n[Experts]",
        "EURUSD=1",
    ],
)
def test_build_startup_plan_rejects_unsafe_symbol(
    symbol,
):
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    bound = service.prepare(
        preflight_result=_preflight(),
        installation_result=_installation(),
    )

    with pytest.raises(ValueError):
        service.build_startup_plan(
            preparation_result=bound,
            symbol=symbol,
        )



def test_gold_first_symbol_resolver_prefers_xauusd_family():
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    symbol = service.select_gold_symbol(
        symbols=(
            "EURUSD",
            "GOLD",
            "XAUUSD.a",
            "XAUUSD",
            "GBPUSD",
        ),
    )

    assert symbol == "XAUUSD"


def test_gold_first_symbol_resolver_prefers_xauusd_variant_over_gold():
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    symbol = service.select_gold_symbol(
        symbols=(
            "EURUSD",
            "GOLD",
            "XAUUSD.a",
        ),
    )

    assert symbol == "XAUUSD.a"


def test_gold_first_symbol_resolver_uses_gold_family_when_no_xauusd():
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    symbol = service.select_gold_symbol(
        symbols=(
            "EURUSD",
            "GOLDm",
            "GBPUSD",
        ),
    )

    assert symbol == "GOLDm"


def test_gold_first_symbol_resolver_fails_closed_without_gold():
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    with pytest.raises(
        RuntimeError,
        match="gold",
    ):
        service.select_gold_symbol(
            symbols=(
                "EURUSD",
                "GBPUSD",
                "USDJPY",
            ),
        )


@pytest.mark.parametrize(
    "symbols",
    [
        (),
        ("",),
        ("   ",),
        ("XAUUSD\n[Experts]",),
        ("XAUUSD=1",),
    ],
)
def test_gold_first_symbol_resolver_rejects_invalid_symbol_surface(
    symbols,
):
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    with pytest.raises(
        ValueError,
    ):
        service.select_gold_symbol(
            symbols=symbols,
        )



def test_render_startup_config_contains_only_bound_startup_intent():
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    bound = service.prepare(
        preflight_result=_preflight(),
        installation_result=_installation(),
    )

    plan = service.build_startup_plan(
        preparation_result=bound,
        symbol="XAUUSD.a",
    )

    rendered = service.render_startup_config(
        startup_plan=plan,
    )

    assert rendered == (
        "[StartUp]\n"
        "Expert=TODOBA_Trusted_Agent\n"
        "Symbol=XAUUSD.a\n"
        "Period=H1\n"
    )


def test_render_startup_config_does_not_embed_credentials_or_trading_authority():
    service = (
        CustomerVPSConnectMT5RuntimePreparationService()
    )

    bound = service.prepare(
        preflight_result=_preflight(),
        installation_result=_installation(),
    )

    plan = service.build_startup_plan(
        preparation_result=bound,
        symbol="XAUUSD",
    )

    rendered = service.render_startup_config(
        startup_plan=plan,
    )

    for forbidden in (
        "Login=",
        "Password=",
        "AllowLiveTrading",
        "Enabled=",
        "WebRequest",
        "AgentSecret",
        "MissionSigningSecret",
        "[Experts]",
        "[Common]",
    ):
        assert forbidden not in rendered


def test_runtime_preparation_owner_has_no_account_or_vps_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_mt5_runtime_preparation_service.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "login(",
        "password",
        "purchase",
        "migrate",
        "MetaTrader5",
        "BrokerStateStore",
        "grant_http_client",
        "live_proof_http_client",
        "common.ini",
        "WebRequestUrl",
        "terminate(",
        "kill(",
    ):
        assert forbidden not in source
