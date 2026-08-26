"""
TODOBA Customer MT5 Setup Preflight Service Tests

R4 contract:

- standard MT5 discovery is filesystem-only and read-only
- discovery never initializes MetaTrader
- stale/malformed origin.txt entries are ignored
- duplicate installation paths collapse to one candidate
- only terminal64.exe is accepted
- preflight probes exactly one explicitly selected terminal
- no MT5 login/password credentials are accepted
- terminal and account truth come from MetaTrader5
- canonical account fingerprint is byte-for-byte:
      <ACCOUNT_SERVER>:<ACCOUNT_LOGIN>
- only ACCOUNT_MARGIN_MODE_RETAIL_HEDGING passes
- NETTING, EXCHANGE, unknown, malformed account state fail closed
- reported terminal must match the selected installation
- reported MT5 data path must exist
- shutdown occurs after every initialize attempt
- no trading operation belongs to R4
"""

from dataclasses import fields
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.commercial.customer_mt5_setup_preflight_service as module
from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5InstallationCandidate,
    CustomerMT5SetupPreflightResult,
    CustomerMT5SetupPreflightService,
)


class FakeMT5:
    ACCOUNT_MARGIN_MODE_RETAIL_NETTING = 0
    ACCOUNT_MARGIN_MODE_EXCHANGE = 1
    ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 2

    def __init__(
        self,
        *,
        initialize_result: bool = True,
        terminal_info_value=None,
        account_info_value=None,
        initialize_error: Exception | None = None,
        terminal_info_error: Exception | None = None,
        account_info_error: Exception | None = None,
    ) -> None:
        self.initialize_result = initialize_result
        self.terminal_info_value = terminal_info_value
        self.account_info_value = account_info_value

        self.initialize_error = initialize_error
        self.terminal_info_error = terminal_info_error
        self.account_info_error = account_info_error

        self.initialize_calls = []
        self.shutdown_calls = 0
        self.terminal_info_calls = 0
        self.account_info_calls = 0

        self.order_send_calls = 0

    def initialize(
        self,
        path,
        *,
        portable=False,
    ):
        self.initialize_calls.append(
            (
                path,
                portable,
            )
        )

        if self.initialize_error is not None:
            raise self.initialize_error

        return self.initialize_result

    def shutdown(
        self,
    ):
        self.shutdown_calls += 1

    def terminal_info(
        self,
    ):
        self.terminal_info_calls += 1

        if self.terminal_info_error is not None:
            raise self.terminal_info_error

        return self.terminal_info_value

    def account_info(
        self,
    ):
        self.account_info_calls += 1

        if self.account_info_error is not None:
            raise self.account_info_error

        return self.account_info_value

    def order_send(
        self,
        request,
    ):
        self.order_send_calls += 1

        raise AssertionError(
            "R4 must never send an MT5 order."
        )


def create_terminal_layout(
    tmp_path: Path,
    *,
    installation_name: str = "MetaTrader 5",
    data_name: str = "MT5 Data",
) -> tuple[
    Path,
    Path,
    Path,
]:
    installation_path = (
        tmp_path
        / installation_name
    )

    installation_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    terminal_path = (
        installation_path
        / "terminal64.exe"
    )

    terminal_path.write_bytes(
        b"test-terminal"
    )

    data_path = (
        tmp_path
        / data_name
    )

    data_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        installation_path,
        terminal_path,
        data_path,
    )


def create_origin(
    roaming_appdata_path: Path,
    *,
    instance_name: str,
    payload: bytes,
) -> Path:
    instance_path = (
        roaming_appdata_path
        / "MetaQuotes"
        / "Terminal"
        / instance_name
    )

    instance_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    origin_path = (
        instance_path
        / "origin.txt"
    )

    origin_path.write_bytes(
        payload
    )

    return origin_path


def build_valid_fake(
    *,
    installation_path: Path,
    data_path: Path,
    login: int = 108292283,
    server: str = "XMGlobal-MT5 5",
    margin_mode: int = 2,
) -> FakeMT5:
    return FakeMT5(
        terminal_info_value=SimpleNamespace(
            path=str(
                installation_path.resolve()
            ),
            data_path=str(
                data_path.resolve()
            ),
        ),
        account_info_value=SimpleNamespace(
            login=login,
            server=server,
            margin_mode=margin_mode,
        ),
    )


def test_installation_candidate_normalizes_outer_whitespace() -> None:
    candidate = CustomerMT5InstallationCandidate(
        installation_path=" C:\\MT5 ",
        terminal_path=" C:\\MT5\\terminal64.exe ",
        origin_path=" C:\\origin.txt ",
        portable=False,
    )

    assert candidate.installation_path == "C:\\MT5"
    assert (
        candidate.terminal_path
        == "C:\\MT5\\terminal64.exe"
    )
    assert candidate.origin_path == "C:\\origin.txt"
    assert candidate.portable is False


@pytest.mark.parametrize(
    "field_name",
    [
        "installation_path",
        "terminal_path",
        "origin_path",
    ],
)
def test_installation_candidate_requires_nonempty_paths(
    field_name: str,
) -> None:
    values = {
        "installation_path": "C:\\MT5",
        "terminal_path": (
            "C:\\MT5\\terminal64.exe"
        ),
        "origin_path": "C:\\origin.txt",
        "portable": False,
    }

    values[
        field_name
    ] = "   "

    with pytest.raises(
        ValueError,
        match=f"{field_name} is required",
    ):
        CustomerMT5InstallationCandidate(
            **values,
        )


def test_installation_candidate_requires_bool_portable() -> None:
    with pytest.raises(
        TypeError,
        match="portable must be bool",
    ):
        CustomerMT5InstallationCandidate(
            installation_path="C:\\MT5",
            terminal_path=(
                "C:\\MT5\\terminal64.exe"
            ),
            origin_path="C:\\origin.txt",
            portable="false",
        )


def test_preflight_result_requires_matching_fingerprint() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "account_fingerprint does not match "
            "server and login"
        ),
    ):
        CustomerMT5SetupPreflightResult(
            terminal_path="C:\\MT5\\terminal64.exe",
            installation_path="C:\\MT5",
            data_path="C:\\MT5Data",
            portable=False,
            login=1001,
            server="Broker-Server",
            margin_mode=2,
            account_fingerprint=(
                "Different-Server:1001"
            ),
        )


def test_preflight_result_requires_positive_integer_login() -> None:
    with pytest.raises(
        ValueError,
        match="login must be greater than zero",
    ):
        CustomerMT5SetupPreflightResult(
            terminal_path="C:\\MT5\\terminal64.exe",
            installation_path="C:\\MT5",
            data_path="C:\\MT5Data",
            portable=False,
            login=0,
            server="Broker-Server",
            margin_mode=2,
            account_fingerprint="Broker-Server:0",
        )


def test_preflight_result_rejects_bool_login() -> None:
    with pytest.raises(
        TypeError,
        match="login must be int",
    ):
        CustomerMT5SetupPreflightResult(
            terminal_path="C:\\MT5\\terminal64.exe",
            installation_path="C:\\MT5",
            data_path="C:\\MT5Data",
            portable=False,
            login=True,
            server="Broker-Server",
            margin_mode=2,
            account_fingerprint="Broker-Server:True",
        )


def test_preflight_result_requires_integer_margin_mode() -> None:
    with pytest.raises(
        TypeError,
        match="margin_mode must be int",
    ):
        CustomerMT5SetupPreflightResult(
            terminal_path="C:\\MT5\\terminal64.exe",
            installation_path="C:\\MT5",
            data_path="C:\\MT5Data",
            portable=False,
            login=1001,
            server="Broker-Server",
            margin_mode="2",
            account_fingerprint=(
                "Broker-Server:1001"
            ),
        )


def test_service_requires_mt5_module() -> None:
    with pytest.raises(
        TypeError,
        match="mt5_module is required",
    ):
        CustomerMT5SetupPreflightService(
            mt5_module=None
        )


@pytest.mark.parametrize(
    "missing_name",
    [
        "initialize",
        "shutdown",
        "terminal_info",
        "account_info",
    ],
)
def test_service_requires_mt5_bridge_functions(
    missing_name: str,
) -> None:
    fake = FakeMT5()

    setattr(
        fake,
        missing_name,
        None,
    )

    with pytest.raises(
        TypeError,
        match=missing_name,
    ):
        CustomerMT5SetupPreflightService(
            mt5_module=fake
        )


def test_service_requires_hedging_constant() -> None:
    fake = SimpleNamespace(
        initialize=lambda *args, **kwargs: True,
        shutdown=lambda: None,
        terminal_info=lambda: None,
        account_info=lambda: None,
    )

    with pytest.raises(
        TypeError,
        match=(
            "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING"
        ),
    ):
        CustomerMT5SetupPreflightService(
            mt5_module=fake
        )


def test_service_uses_injected_hedging_constant_not_magic_number(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
        margin_mode=77,
    )

    fake.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 77

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    result = service.preflight(
        terminal_path=terminal_path,
        portable=False,
    )

    assert result.margin_mode == 77


def test_discovery_requires_path() -> None:
    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    with pytest.raises(
        TypeError,
        match="roaming_appdata_path must be Path",
    ):
        service.discover_standard_installations(
            roaming_appdata_path="C:\\Users\\Test\\AppData"
        )


def test_discovery_returns_empty_when_terminal_root_missing(
    tmp_path: Path,
) -> None:
    fake = FakeMT5()

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    result = (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
    )

    assert result == ()
    assert fake.initialize_calls == []
    assert fake.shutdown_calls == 0


def test_discovery_returns_empty_when_terminal_root_is_file(
    tmp_path: Path,
) -> None:
    fake = FakeMT5()

    terminal_root = (
        tmp_path
        / "MetaQuotes"
        / "Terminal"
    )

    terminal_root.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    terminal_root.write_text(
        "not-a-directory",
        encoding="utf-8",
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    assert (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
        == ()
    )

    assert fake.initialize_calls == []


def test_discovery_reads_valid_utf8_origin(
    tmp_path: Path,
) -> None:
    fake = FakeMT5()

    (
        installation_path,
        terminal_path,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    origin_path = create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=str(
            installation_path
        ).encode(
            "utf-8"
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    result = (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
    )

    assert len(
        result
    ) == 1

    candidate = result[
        0
    ]

    assert (
        candidate.installation_path
        == str(
            installation_path.resolve()
        )
    )

    assert (
        candidate.terminal_path
        == str(
            terminal_path.resolve()
        )
    )

    assert (
        candidate.origin_path
        == str(
            origin_path.resolve()
        )
    )

    assert candidate.portable is False

    assert fake.initialize_calls == []
    assert fake.shutdown_calls == 0


def test_discovery_accepts_utf8_bom_origin(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        _,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=(
            b"\xef\xbb\xbf"
            + str(
                installation_path
            ).encode(
                "utf-8"
            )
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    result = (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
    )

    assert len(
        result
    ) == 1


def test_discovery_accepts_utf16_origin(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        _,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=str(
            installation_path
        ).encode(
            "utf-16"
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    result = (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
    )

    assert len(
        result
    ) == 1


def test_discovery_accepts_utf16le_without_bom(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        _,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=str(
            installation_path
        ).encode(
            "utf-16-le"
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    result = (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
    )

    assert len(
        result
    ) == 1


def test_discovery_trims_origin_outer_whitespace(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        _,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=(
            f"\r\n  {installation_path}  \r\n"
        ).encode(
            "utf-8"
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    result = (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
    )

    assert len(
        result
    ) == 1


def test_discovery_ignores_empty_origin(
    tmp_path: Path,
) -> None:
    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=b"",
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    assert (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
        == ()
    )


def test_discovery_ignores_invalid_origin_encoding(
    tmp_path: Path,
) -> None:
    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=b"\x80\x81\x82",
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    assert (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
        == ()
    )


def test_discovery_ignores_stale_installation_path(
    tmp_path: Path,
) -> None:
    missing = (
        tmp_path
        / "missing-installation"
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=str(
            missing
        ).encode(
            "utf-8"
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    assert (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
        == ()
    )


def test_discovery_ignores_installation_without_terminal64(
    tmp_path: Path,
) -> None:
    installation_path = (
        tmp_path
        / "MetaTrader 5"
    )

    installation_path.mkdir()

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=str(
            installation_path
        ).encode(
            "utf-8"
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    assert (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
        == ()
    )


def test_discovery_ignores_terminal32_only_installation(
    tmp_path: Path,
) -> None:
    installation_path = (
        tmp_path
        / "MetaTrader 5"
    )

    installation_path.mkdir()

    (
        installation_path
        / "terminal.exe"
    ).write_bytes(
        b"32-bit-terminal"
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=str(
            installation_path
        ).encode(
            "utf-8"
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    assert (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
        == ()
    )


def test_discovery_deduplicates_same_installation(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        _,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    payload = str(
        installation_path
    ).encode(
        "utf-8"
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=payload,
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE002",
        payload=payload,
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    result = (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
    )

    assert len(
        result
    ) == 1


def test_discovery_keeps_different_installations(
    tmp_path: Path,
) -> None:
    (
        first_install,
        _,
        _,
    ) = create_terminal_layout(
        tmp_path,
        installation_name="MT5 A",
        data_name="Data A",
    )

    (
        second_install,
        _,
        _,
    ) = create_terminal_layout(
        tmp_path,
        installation_name="MT5 B",
        data_name="Data B",
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=str(
            first_install
        ).encode(
            "utf-8"
        ),
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE002",
        payload=str(
            second_install
        ).encode(
            "utf-8"
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=FakeMT5()
    )

    result = (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
    )

    assert len(
        result
    ) == 2


def test_discovery_never_initializes_mt5(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        _,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    create_origin(
        tmp_path,
        instance_name="INSTANCE001",
        payload=str(
            installation_path
        ).encode(
            "utf-8"
        ),
    )

    fake = FakeMT5(
        initialize_error=AssertionError(
            "Discovery must never initialize MT5."
        )
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    result = (
        service.discover_standard_installations(
            roaming_appdata_path=tmp_path
        )
    )

    assert len(
        result
    ) == 1
    assert fake.initialize_calls == []
    assert fake.shutdown_calls == 0


def test_preflight_requires_terminal_path_object(
    tmp_path: Path,
) -> None:
    fake = FakeMT5()

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        TypeError,
        match="terminal_path must be Path",
    ):
        service.preflight(
            terminal_path="C:\\MT5\\terminal64.exe",
            portable=False,
        )

    assert fake.initialize_calls == []


def test_preflight_rejects_missing_terminal(
    tmp_path: Path,
) -> None:
    fake = FakeMT5()

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        ValueError,
        match="does not exist",
    ):
        service.preflight(
            terminal_path=(
                tmp_path
                / "terminal64.exe"
            ),
            portable=False,
        )

    assert fake.initialize_calls == []
    assert fake.shutdown_calls == 0


def test_preflight_rejects_terminal_path_that_is_directory(
    tmp_path: Path,
) -> None:
    terminal_path = (
        tmp_path
        / "terminal64.exe"
    )

    terminal_path.mkdir()

    fake = FakeMT5()

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        ValueError,
        match="must be a file",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.initialize_calls == []


def test_preflight_rejects_wrong_executable_name(
    tmp_path: Path,
) -> None:
    terminal_path = (
        tmp_path
        / "other.exe"
    )

    terminal_path.write_bytes(
        b"test"
    )

    fake = FakeMT5()

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        ValueError,
        match="must be terminal64.exe",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.initialize_calls == []


def test_preflight_requires_bool_portable(
    tmp_path: Path,
) -> None:
    (
        _,
        terminal_path,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5()

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        TypeError,
        match="portable must be bool",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable="false",
        )

    assert fake.initialize_calls == []


def test_preflight_initializes_exact_selected_terminal(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    service.preflight(
        terminal_path=terminal_path,
        portable=False,
    )

    assert fake.initialize_calls == [
        (
            str(
                terminal_path.resolve()
            ),
            False,
        )
    ]


def test_preflight_passes_portable_true_explicitly(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    result = service.preflight(
        terminal_path=terminal_path,
        portable=True,
    )

    assert fake.initialize_calls == [
        (
            str(
                terminal_path.resolve()
            ),
            True,
        )
    ]

    assert result.portable is True


def test_preflight_builds_authoritative_hedging_result(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
        login=108292283,
        server="XMGlobal-MT5 5",
        margin_mode=(
            FakeMT5
            .ACCOUNT_MARGIN_MODE_RETAIL_HEDGING
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    result = service.preflight(
        terminal_path=terminal_path,
        portable=False,
    )

    assert (
        result.terminal_path
        == str(
            terminal_path.resolve()
        )
    )

    assert (
        result.installation_path
        == str(
            installation_path.resolve()
        )
    )

    assert (
        result.data_path
        == str(
            data_path.resolve()
        )
    )

    assert result.login == 108292283
    assert result.server == "XMGlobal-MT5 5"

    assert (
        result.margin_mode
        == FakeMT5
        .ACCOUNT_MARGIN_MODE_RETAIL_HEDGING
    )

    assert (
        result.account_fingerprint
        == "XMGlobal-MT5 5:108292283"
    )

    assert fake.shutdown_calls == 1
    assert fake.order_send_calls == 0


def test_preflight_preserves_server_byte_for_byte(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    server = "XMGlobal-MT5 5"

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
        server=server,
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    result = service.preflight(
        terminal_path=terminal_path,
        portable=False,
    )

    assert result.server == server
    assert (
        result.account_fingerprint
        == f"{server}:108292283"
    )


@pytest.mark.parametrize(
    "margin_mode",
    [
        FakeMT5.ACCOUNT_MARGIN_MODE_RETAIL_NETTING,
        FakeMT5.ACCOUNT_MARGIN_MODE_EXCHANGE,
        999,
        -1,
    ],
)
def test_preflight_rejects_non_hedging_margin_modes(
    tmp_path: Path,
    margin_mode: int,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
        margin_mode=margin_mode,
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        ValueError,
        match="requires an MT5 HEDGING account",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


@pytest.mark.parametrize(
    "login",
    [
        0,
        -1,
        True,
        None,
        "108292283",
    ],
)
def test_preflight_rejects_invalid_account_login(
    tmp_path: Path,
    login,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
    )

    fake.account_info_value.login = login

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="account login is invalid",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


@pytest.mark.parametrize(
    "server",
    [
        "",
        None,
        123,
    ],
)
def test_preflight_rejects_invalid_account_server(
    tmp_path: Path,
    server,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
    )

    fake.account_info_value.server = server

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="account server",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


@pytest.mark.parametrize(
    "margin_mode",
    [
        None,
        True,
        "2",
    ],
)
def test_preflight_rejects_invalid_margin_mode_type(
    tmp_path: Path,
    margin_mode,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
    )

    fake.account_info_value.margin_mode = (
        margin_mode
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="margin mode is invalid",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_fails_when_initialize_returns_false(
    tmp_path: Path,
) -> None:
    (
        _,
        terminal_path,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5(
        initialize_result=False
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to initialize selected",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert len(
        fake.initialize_calls
    ) == 1

    assert fake.shutdown_calls == 1


def test_preflight_shutdown_runs_when_initialize_raises(
    tmp_path: Path,
) -> None:
    (
        _,
        terminal_path,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5(
        initialize_error=RuntimeError(
            "simulated initialize error"
        )
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="simulated initialize error",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_fails_when_terminal_info_missing(
    tmp_path: Path,
) -> None:
    (
        _,
        terminal_path,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5(
        terminal_info_value=None
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="terminal information",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.account_info_calls == 0
    assert fake.shutdown_calls == 1


def test_preflight_shutdown_runs_when_terminal_info_raises(
    tmp_path: Path,
) -> None:
    (
        _,
        terminal_path,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5(
        terminal_info_error=RuntimeError(
            "simulated terminal_info error"
        )
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="simulated terminal_info error",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_fails_when_account_info_missing(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5(
        terminal_info_value=SimpleNamespace(
            path=str(
                installation_path.resolve()
            ),
            data_path=str(
                data_path.resolve()
            ),
        ),
        account_info_value=None,
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="no readable active account",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_shutdown_runs_when_account_info_raises(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5(
        terminal_info_value=SimpleNamespace(
            path=str(
                installation_path.resolve()
            ),
            data_path=str(
                data_path.resolve()
            ),
        ),
        account_info_error=RuntimeError(
            "simulated account_info error"
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="simulated account_info error",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_rejects_missing_reported_terminal_path(
    tmp_path: Path,
) -> None:
    (
        _,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5(
        terminal_info_value=SimpleNamespace(
            path=None,
            data_path=str(
                data_path
            ),
        ),
        account_info_value=SimpleNamespace(
            login=1001,
            server="Broker",
            margin_mode=2,
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="terminal installation path",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_rejects_missing_reported_data_path(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5(
        terminal_info_value=SimpleNamespace(
            path=str(
                installation_path
            ),
            data_path=None,
        ),
        account_info_value=SimpleNamespace(
            login=1001,
            server="Broker",
            margin_mode=2,
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="terminal data path",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_rejects_nonexistent_reported_path(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = FakeMT5(
        terminal_info_value=SimpleNamespace(
            path=str(
                installation_path
            ),
            data_path=str(
                tmp_path
                / "missing-data"
            ),
        ),
        account_info_value=SimpleNamespace(
            login=1001,
            server="Broker",
            margin_mode=2,
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "reported an invalid terminal or data path"
        ),
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_rejects_reported_terminal_path_that_is_file(
    tmp_path: Path,
) -> None:
    (
        _,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    reported_path = (
        tmp_path
        / "reported-terminal-path"
    )

    reported_path.write_text(
        "not-directory",
        encoding="utf-8",
    )

    fake = FakeMT5(
        terminal_info_value=SimpleNamespace(
            path=str(
                reported_path
            ),
            data_path=str(
                data_path
            ),
        ),
        account_info_value=SimpleNamespace(
            login=1001,
            server="Broker",
            margin_mode=2,
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="terminal path is not a directory",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_rejects_reported_data_path_that_is_file(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        _,
    ) = create_terminal_layout(
        tmp_path
    )

    data_file = (
        tmp_path
        / "data-file"
    )

    data_file.write_text(
        "not-directory",
        encoding="utf-8",
    )

    fake = FakeMT5(
        terminal_info_value=SimpleNamespace(
            path=str(
                installation_path
            ),
            data_path=str(
                data_file
            ),
        ),
        account_info_value=SimpleNamespace(
            login=1001,
            server="Broker",
            margin_mode=2,
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match="data path is not a directory",
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_rejects_different_initialized_terminal(
    tmp_path: Path,
) -> None:
    (
        _,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path,
        installation_name="Selected MT5",
    )

    different_installation = (
        tmp_path
        / "Different MT5"
    )

    different_installation.mkdir()

    fake = FakeMT5(
        terminal_info_value=SimpleNamespace(
            path=str(
                different_installation.resolve()
            ),
            data_path=str(
                data_path.resolve()
            ),
        ),
        account_info_value=SimpleNamespace(
            login=1001,
            server="Broker",
            margin_mode=2,
        ),
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "initialized a different terminal"
        ),
    ):
        service.preflight(
            terminal_path=terminal_path,
            portable=False,
        )

    assert fake.shutdown_calls == 1


def test_preflight_never_calls_trading_operation(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    service.preflight(
        terminal_path=terminal_path,
        portable=False,
    )

    assert fake.order_send_calls == 0


def test_preflight_result_contains_only_r4_truth() -> None:
    result_fields = {
        item.name
        for item in fields(
            CustomerMT5SetupPreflightResult
        )
    }

    assert result_fields == {
        "terminal_path",
        "installation_path",
        "data_path",
        "portable",
        "login",
        "server",
        "margin_mode",
        "account_fingerprint",
    }

    forbidden = {
        "customer_id",
        "setup_activation_id",
        "handoff_id",
        "handoff_credential",
        "password",
        "investor_password",
        "master_password",
        "deployment_id",
        "agent_id",
        "credential_id",
        "access_credential",
        "payment_id",
        "subscription_id",
        "package",
        "entitlement",
    }

    assert forbidden.isdisjoint(
        result_fields
    )


def test_discovery_contract_has_no_customer_or_secret_inputs() -> None:
    parameters = inspect.signature(
        CustomerMT5SetupPreflightService
        .discover_standard_installations
    ).parameters

    assert tuple(
        parameters
    ) == (
        "self",
        "roaming_appdata_path",
    )


def test_preflight_contract_has_only_selected_terminal_and_mode() -> None:
    parameters = inspect.signature(
        CustomerMT5SetupPreflightService
        .preflight
    ).parameters

    assert tuple(
        parameters
    ) == (
        "self",
        "terminal_path",
        "portable",
    )

    forbidden = {
        "customer_id",
        "setup_activation_id",
        "handoff_credential",
        "login",
        "server",
        "password",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
        "package",
    }

    assert forbidden.isdisjoint(
        parameters
    )


def test_r4_owner_does_not_import_trading_runtime() -> None:
    source = inspect.getsource(
        module
    )

    assert "backend.trading" not in source
    assert "backend.runtime" not in source


def test_r4_owner_does_not_import_metatrader5_directly() -> None:
    source = inspect.getsource(
        module
    )

    assert "import MetaTrader5" not in source
    assert "from MetaTrader5" not in source


def test_r4_owner_has_no_persistence_owner() -> None:
    source = inspect.getsource(
        module
    )

    assert "json.dump" not in source
    assert "write_text(" not in source
    assert "write_bytes(" not in source
    assert "os.replace(" not in source


def test_windows_path_key_is_case_insensitive() -> None:
    first = (
        CustomerMT5SetupPreflightService
        ._windows_path_key(
            Path(
                "C:/Program Files/MetaTrader 5/"
                "terminal64.exe"
            )
        )
    )

    second = (
        CustomerMT5SetupPreflightService
        ._windows_path_key(
            Path(
                "c:\\program files\\metatrader 5\\"
                "TERMINAL64.EXE"
            )
        )
    )

    assert first == second


def test_shutdown_occurs_once_after_success(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    fake = build_valid_fake(
        installation_path=installation_path,
        data_path=data_path,
    )

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    service.preflight(
        terminal_path=terminal_path,
        portable=False,
    )

    assert fake.shutdown_calls == 1


def test_preflight_reads_terminal_before_account(
    tmp_path: Path,
) -> None:
    (
        installation_path,
        terminal_path,
        data_path,
    ) = create_terminal_layout(
        tmp_path
    )

    calls = []

    class OrderedFakeMT5(
        FakeMT5
    ):
        def terminal_info(
            self,
        ):
            calls.append(
                "terminal_info"
            )

            return SimpleNamespace(
                path=str(
                    installation_path.resolve()
                ),
                data_path=str(
                    data_path.resolve()
                ),
            )

        def account_info(
            self,
        ):
            calls.append(
                "account_info"
            )

            return SimpleNamespace(
                login=1001,
                server="Broker",
                margin_mode=2,
            )

    fake = OrderedFakeMT5()

    service = CustomerMT5SetupPreflightService(
        mt5_module=fake
    )

    service.preflight(
        terminal_path=terminal_path,
        portable=False,
    )

    assert calls == [
        "terminal_info",
        "account_info",
    ]