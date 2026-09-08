from pathlib import Path

import pytest

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5InstallationCandidate,
    CustomerMT5SetupPreflightService,
)

from backend.commercial.customer_vps_connect_mt5_detection_service import (
    CustomerVPSConnectMT5DetectionOption,
    CustomerVPSConnectMT5DetectionResult,
    CustomerVPSConnectMT5DetectionService,
)


ROAMING = Path(r"C:\Users\Customer\AppData\Roaming")

INSTALL_A = r"C:\Program Files\MetaTrader 5"
TERMINAL_A = INSTALL_A + r"\terminal64.exe"
ORIGIN_A = (
    r"C:\Users\Customer\AppData\Roaming"
    r"\MetaQuotes\Terminal\AAA\origin.txt"
)

INSTALL_B = r"D:\Broker MT5"
TERMINAL_B = INSTALL_B + r"\terminal64.exe"
ORIGIN_B = (
    r"C:\Users\Customer\AppData\Roaming"
    r"\MetaQuotes\Terminal\BBB\origin.txt"
)


class FakePreflightService(
    CustomerMT5SetupPreflightService
):
    def __init__(
        self,
        candidates,
    ):
        self.candidates = candidates
        self.calls = []

    def discover_standard_installations(
        self,
        *,
        roaming_appdata_path,
    ):
        self.calls.append(
            roaming_appdata_path
        )
        return self.candidates


def _candidate(
    *,
    installation_path,
    terminal_path,
    origin_path,
):
    return CustomerMT5InstallationCandidate(
        installation_path=installation_path,
        terminal_path=terminal_path,
        origin_path=origin_path,
        portable=False,
    )


def test_detect_projects_customer_safe_installations():
    preflight = FakePreflightService(
        (
            _candidate(
                installation_path=INSTALL_A,
                terminal_path=TERMINAL_A,
                origin_path=ORIGIN_A,
            ),
            _candidate(
                installation_path=INSTALL_B,
                terminal_path=TERMINAL_B,
                origin_path=ORIGIN_B,
            ),
        )
    )

    service = CustomerVPSConnectMT5DetectionService(
        mt5_preflight_service=preflight,
    )

    result = service.detect(
        roaming_appdata_path=ROAMING,
    )

    assert preflight.calls == [ROAMING]

    assert result == CustomerVPSConnectMT5DetectionResult(
        status="detected",
        installations=(
            CustomerVPSConnectMT5DetectionOption(
                installation_path=INSTALL_A,
                terminal_path=TERMINAL_A,
                portable=False,
            ),
            CustomerVPSConnectMT5DetectionOption(
                installation_path=INSTALL_B,
                terminal_path=TERMINAL_B,
                portable=False,
            ),
        ),
    )

    assert not hasattr(
        result.installations[0],
        "origin_path",
    )

    assert ORIGIN_A not in repr(result)
    assert ORIGIN_B not in repr(result)


def test_no_installations_returns_not_found():
    preflight = FakePreflightService(
        ()
    )

    service = CustomerVPSConnectMT5DetectionService(
        mt5_preflight_service=preflight,
    )

    result = service.detect(
        roaming_appdata_path=ROAMING,
    )

    assert result == CustomerVPSConnectMT5DetectionResult(
        status="not_found",
        installations=(),
    )


def test_invalid_discovery_result_fails_closed():
    preflight = FakePreflightService(
        []
    )

    service = CustomerVPSConnectMT5DetectionService(
        mt5_preflight_service=preflight,
    )

    with pytest.raises(RuntimeError):
        service.detect(
            roaming_appdata_path=ROAMING,
        )


def test_invalid_candidate_fails_closed():
    preflight = FakePreflightService(
        (
            object(),
        )
    )

    service = CustomerVPSConnectMT5DetectionService(
        mt5_preflight_service=preflight,
    )

    with pytest.raises(RuntimeError):
        service.detect(
            roaming_appdata_path=ROAMING,
        )


def test_roaming_appdata_path_must_be_path():
    preflight = FakePreflightService(
        ()
    )

    service = CustomerVPSConnectMT5DetectionService(
        mt5_preflight_service=preflight,
    )

    with pytest.raises(TypeError):
        service.detect(
            roaming_appdata_path=str(ROAMING),
        )

    assert preflight.calls == []


def test_constructor_requires_preflight_owner():
    with pytest.raises(TypeError):
        CustomerVPSConnectMT5DetectionService(
            mt5_preflight_service=object(),
        )


@pytest.mark.parametrize(
    "status,installations",
    [
        (
            "detected",
            (),
        ),
        (
            "not_found",
            (
                CustomerVPSConnectMT5DetectionOption(
                    installation_path=INSTALL_A,
                    terminal_path=TERMINAL_A,
                    portable=False,
                ),
            ),
        ),
        (
            "unknown",
            (),
        ),
    ],
)
def test_detection_result_invariants(
    status,
    installations,
):
    with pytest.raises(ValueError):
        CustomerVPSConnectMT5DetectionResult(
            status=status,
            installations=installations,
        )


def test_owner_has_no_extra_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_mt5_detection_service.py"
    ).read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "backend.main",
        "CustomerVPSConnectGrantStore",
        "grant_credential",
        "activation_code",
        "account_fingerprint",
        "MetaTrader5.initialize",
        "write_text",
        "write_bytes",
        "initialize_empty",
    ):
        assert forbidden not in source
