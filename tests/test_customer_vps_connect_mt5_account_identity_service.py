from pathlib import Path

import pytest

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
    CustomerMT5SetupPreflightService,
)

from backend.commercial.customer_vps_connect_mt5_detection_service import (
    CustomerVPSConnectMT5DetectionOption,
)

from backend.commercial.customer_vps_connect_mt5_account_identity_service import (
    CustomerVPSConnectMT5AccountIdentityResult,
    CustomerVPSConnectMT5AccountIdentityService,
)


INSTALLATION_PATH = r"C:\Program Files\MetaTrader 5"
TERMINAL_PATH = INSTALLATION_PATH + r"\terminal64.exe"
DATA_PATH = (
    r"C:\Users\Customer\AppData\Roaming"
    r"\MetaQuotes\Terminal\ABC123"
)

LOGIN = 68351319
SERVER = "RoboForex-Pro"
FINGERPRINT = f"{SERVER}:{LOGIN}"
HEDGING_MARGIN_MODE = 2


def _option():
    return CustomerVPSConnectMT5DetectionOption(
        installation_path=INSTALLATION_PATH,
        terminal_path=TERMINAL_PATH,
        portable=False,
    )


def _result(
    *,
    terminal_path=TERMINAL_PATH,
    installation_path=INSTALLATION_PATH,
    portable=False,
    login=LOGIN,
    server=SERVER,
    account_fingerprint=FINGERPRINT,
):
    return CustomerMT5SetupPreflightResult(
        terminal_path=terminal_path,
        installation_path=installation_path,
        data_path=DATA_PATH,
        portable=portable,
        login=login,
        server=server,
        margin_mode=HEDGING_MARGIN_MODE,
        account_fingerprint=account_fingerprint,
    )


class FakePreflightService(
    CustomerMT5SetupPreflightService
):
    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    def preflight(
        self,
        *,
        terminal_path,
        portable,
    ):
        self.calls.append(
            (
                terminal_path,
                portable,
            )
        )
        return self.result


def test_probe_reuses_existing_preflight_and_projects_identity():
    preflight = FakePreflightService(
        _result()
    )

    service = CustomerVPSConnectMT5AccountIdentityService(
        mt5_preflight_service=preflight,
    )

    result = service.probe(
        option=_option(),
    )

    assert preflight.calls == [
        (
            Path(TERMINAL_PATH),
            False,
        )
    ]

    assert result == CustomerVPSConnectMT5AccountIdentityResult(
        status="account_ready",
        terminal_path=TERMINAL_PATH,
        login=LOGIN,
        server=SERVER,
        account_fingerprint=FINGERPRINT,
    )

    assert not hasattr(
        result,
        "data_path",
    )

    assert not hasattr(
        result,
        "margin_mode",
    )


def test_invalid_preflight_result_fails_closed():
    preflight = FakePreflightService(
        object()
    )

    service = CustomerVPSConnectMT5AccountIdentityService(
        mt5_preflight_service=preflight,
    )

    with pytest.raises(RuntimeError):
        service.probe(
            option=_option(),
        )


@pytest.mark.parametrize(
    "preflight_result",
    [
        _result(
            terminal_path=(
                r"D:\Other MT5\terminal64.exe"
            )
        ),
        _result(
            installation_path=(
                r"D:\Other MT5"
            )
        ),
        _result(
            portable=True
        ),
    ],
)
def test_selected_terminal_identity_must_converge(
    preflight_result,
):
    preflight = FakePreflightService(
        preflight_result
    )

    service = CustomerVPSConnectMT5AccountIdentityService(
        mt5_preflight_service=preflight,
    )

    with pytest.raises(
        RuntimeError,
        match="identity",
    ):
        service.probe(
            option=_option(),
        )


def test_account_fingerprint_must_be_canonical():
    corrupted_result = _result()

    object.__setattr__(
        corrupted_result,
        "account_fingerprint",
        "wrong:fingerprint",
    )

    preflight = FakePreflightService(
        corrupted_result
    )

    service = CustomerVPSConnectMT5AccountIdentityService(
        mt5_preflight_service=preflight,
    )

    with pytest.raises(
        RuntimeError,
        match="fingerprint",
    ):
        service.probe(
            option=_option(),
        )


def test_constructor_requires_existing_preflight_owner():
    with pytest.raises(TypeError):
        CustomerVPSConnectMT5AccountIdentityService(
            mt5_preflight_service=object(),
        )


def test_probe_requires_detection_option():
    preflight = FakePreflightService(
        _result()
    )

    service = CustomerVPSConnectMT5AccountIdentityService(
        mt5_preflight_service=preflight,
    )

    with pytest.raises(TypeError):
        service.probe(
            option=object(),
        )

    assert preflight.calls == []


@pytest.mark.parametrize(
    "status,terminal_path,login,server,fingerprint",
    [
        (
            "unknown",
            TERMINAL_PATH,
            LOGIN,
            SERVER,
            FINGERPRINT,
        ),
        (
            "account_ready",
            "",
            LOGIN,
            SERVER,
            FINGERPRINT,
        ),
        (
            "account_ready",
            TERMINAL_PATH,
            0,
            SERVER,
            FINGERPRINT,
        ),
        (
            "account_ready",
            TERMINAL_PATH,
            LOGIN,
            "",
            FINGERPRINT,
        ),
        (
            "account_ready",
            TERMINAL_PATH,
            LOGIN,
            SERVER,
            "",
        ),
    ],
)
def test_result_invariants(
    status,
    terminal_path,
    login,
    server,
    fingerprint,
):
    with pytest.raises(
        (TypeError, ValueError),
    ):
        CustomerVPSConnectMT5AccountIdentityResult(
            status=status,
            terminal_path=terminal_path,
            login=login,
            server=server,
            account_fingerprint=fingerprint,
        )


def test_owner_does_not_duplicate_mt5_or_gain_extra_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_mt5_account_identity_service.py"
    ).read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "backend.main",
        "MetaTrader5.initialize",
        "grant_credential",
        "activation_code",
        "CustomerVPSConnectGrantStore",
        "write_text",
        "write_bytes",
        "initialize_empty",
    ):
        assert forbidden not in source

    for forbidden_password_surface in (
        "self._password",
        "password=",
        "password:",
        '"password":',
        "'password':",
    ):
        assert forbidden_password_surface not in source


def test_probe_binding_preserves_internal_authoritative_preflight():
    preflight_result = _result()

    preflight_service = FakePreflightService(
        preflight_result
    )

    service = (
        CustomerVPSConnectMT5AccountIdentityService(
            mt5_preflight_service=preflight_service,
        )
    )

    binding = service.probe_binding(
        option=_option(),
    )

    assert binding.identity.status == "account_ready"

    assert (
        binding.identity.account_fingerprint
        == preflight_result.account_fingerprint
    )

    assert (
        binding.preflight_result
        is preflight_result
    )


def test_probe_remains_customer_safe_after_internal_binding_support():
    preflight_service = FakePreflightService(
        _result()
    )

    service = (
        CustomerVPSConnectMT5AccountIdentityService(
            mt5_preflight_service=preflight_service,
        )
    )

    result = service.probe(
        option=_option(),
    )

    assert not hasattr(
        result,
        "data_path",
    )

    assert not hasattr(
        result,
        "preflight_result",
    )
