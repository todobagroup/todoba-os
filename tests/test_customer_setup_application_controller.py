"""
Owner tests for Customer Setup Application Controller.
"""

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallationResult,
    CustomerMT5EX5InstallerService,
)
from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5InstallationCandidate,
    CustomerMT5SetupPreflightResult,
    CustomerMT5SetupPreflightService,
)
from backend.commercial.customer_setup_application_controller import (
    CustomerSetupApplicationController,
    CustomerSetupApplicationResult,
    CustomerSetupInstallationOption,
)
from backend.commercial.customer_setup_http_client import (
    CustomerSetupHttpClient,
)
from backend.commercial.customer_setup_orchestration_service import (
    CustomerSetupOrchestrationResult,
    CustomerSetupOrchestrationService,
)


LOGIN = 12345678
SERVER = "Broker-Server"
ACCOUNT_FINGERPRINT = (
    f"{SERVER}:{LOGIN}"
)
ARTIFACT_BYTES = b"TODOBA EX5"
ARTIFACT_SHA256 = hashlib.sha256(
    ARTIFACT_BYTES
).hexdigest()
ARTIFACT_SIZE_BYTES = len(
    ARTIFACT_BYTES
)


def _preflight_service(
) -> CustomerMT5SetupPreflightService:
    fake_mt5 = SimpleNamespace(
        initialize=lambda **kwargs: True,
        shutdown=lambda: None,
        terminal_info=lambda: None,
        account_info=lambda: None,
        ACCOUNT_MARGIN_MODE_RETAIL_HEDGING=2,
    )

    return CustomerMT5SetupPreflightService(
        mt5_module=fake_mt5
    )


def _orchestration_service(
) -> CustomerSetupOrchestrationService:
    http_client = CustomerSetupHttpClient(
        setup_base_url=(
            "https://api.todobagroup.com"
        ),
        setup_handoff_credential=(
            "tdbsh1.test-secret"
        ),
    )

    installer = (
        CustomerMT5EX5InstallerService()
    )

    return CustomerSetupOrchestrationService(
        setup_http_client=http_client,
        ex5_installer_service=installer,
    )


def _controller():
    preflight_service = (
        _preflight_service()
    )
    orchestration_service = (
        _orchestration_service()
    )

    controller = (
        CustomerSetupApplicationController(
            mt5_preflight_service=(
                preflight_service
            ),
            setup_orchestration_service=(
                orchestration_service
            ),
        )
    )

    return (
        preflight_service,
        orchestration_service,
        controller,
    )


def _paths(
    tmp_path: Path,
):
    installation_path = (
        tmp_path
        / "MT5"
    )
    installation_path.mkdir()

    terminal_path = (
        installation_path
        / "terminal64.exe"
    )
    terminal_path.write_bytes(
        b"terminal"
    )

    data_path = (
        tmp_path
        / "MT5Data"
    )
    data_path.mkdir()

    origin_path = (
        tmp_path
        / "origin.txt"
    )
    origin_path.write_text(
        str(
            installation_path
        ),
        encoding="utf-8",
    )

    return (
        installation_path,
        terminal_path,
        data_path,
        origin_path,
    )


def _candidate(
    tmp_path: Path,
) -> CustomerMT5InstallationCandidate:
    (
        installation_path,
        terminal_path,
        _,
        origin_path,
    ) = _paths(
        tmp_path
    )

    return CustomerMT5InstallationCandidate(
        installation_path=str(
            installation_path.resolve()
        ),
        terminal_path=str(
            terminal_path.resolve()
        ),
        origin_path=str(
            origin_path.resolve()
        ),
        portable=False,
    )


def _option(
    tmp_path: Path,
) -> CustomerSetupInstallationOption:
    candidate = _candidate(
        tmp_path
    )

    return CustomerSetupInstallationOption(
        installation_path=(
            candidate.installation_path
        ),
        terminal_path=(
            candidate.terminal_path
        ),
        portable=candidate.portable,
    )


def _preflight_result(
    tmp_path: Path,
) -> CustomerMT5SetupPreflightResult:
    installation_path = (
        tmp_path
        / "MT5"
    )
    terminal_path = (
        installation_path
        / "terminal64.exe"
    )
    data_path = (
        tmp_path
        / "MT5Data"
    )

    return CustomerMT5SetupPreflightResult(
        terminal_path=str(
            terminal_path.resolve()
        ),
        installation_path=str(
            installation_path.resolve()
        ),
        data_path=str(
            data_path.resolve()
        ),
        portable=False,
        login=LOGIN,
        server=SERVER,
        margin_mode=2,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )


def _installation_result(
    *,
    preflight_result: CustomerMT5SetupPreflightResult,
    tmp_path: Path,
    terminal_path: str | None = None,
    account_fingerprint: str = ACCOUNT_FINGERPRINT,
) -> CustomerMT5EX5InstallationResult:
    experts_path = (
        Path(
            preflight_result.data_path
        )
        / "MQL5"
        / "Experts"
    )
    experts_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    installed_path = (
        experts_path
        / "TODOBA_Trusted_Agent.ex5"
    )
    installed_path.write_bytes(
        ARTIFACT_BYTES
    )

    return CustomerMT5EX5InstallationResult(
        terminal_path=(
            preflight_result.terminal_path
            if terminal_path is None
            else terminal_path
        ),
        data_path=(
            preflight_result.data_path
        ),
        account_fingerprint=(
            account_fingerprint
        ),
        installed_path=str(
            installed_path.resolve()
        ),
        artifact_sha256=(
            ARTIFACT_SHA256
        ),
        artifact_size_bytes=(
            ARTIFACT_SIZE_BYTES
        ),
        already_present=False,
    )


def test_discovery_projects_customer_safe_options(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate = _candidate(
        tmp_path
    )

    preflight_service, _, controller = (
        _controller()
    )

    captured = {}

    def discover(
        *,
        roaming_appdata_path,
    ):
        captured[
            "roaming_appdata_path"
        ] = roaming_appdata_path

        return (
            candidate,
        )

    monkeypatch.setattr(
        preflight_service,
        "discover_standard_installations",
        discover,
    )

    roaming_path = (
        tmp_path
        / "Roaming"
    )
    roaming_path.mkdir()

    result = (
        controller
        .discover_standard_installations(
            roaming_appdata_path=(
                roaming_path
            )
        )
    )

    assert result == (
        CustomerSetupInstallationOption(
            installation_path=(
                candidate.installation_path
            ),
            terminal_path=(
                candidate.terminal_path
            ),
            portable=False,
        ),
    )

    assert (
        captured[
            "roaming_appdata_path"
        ]
        is roaming_path
    )

    assert not hasattr(
        result[0],
        "origin_path",
    )


def test_discovery_empty_is_safe_empty_tuple(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight_service, _, controller = (
        _controller()
    )

    monkeypatch.setattr(
        preflight_service,
        "discover_standard_installations",
        lambda **kwargs: (),
    )

    roaming_path = (
        tmp_path
        / "Roaming"
    )
    roaming_path.mkdir()

    assert (
        controller
        .discover_standard_installations(
            roaming_appdata_path=(
                roaming_path
            )
        )
        == ()
    )


def test_discovery_requires_path() -> None:
    _, _, controller = _controller()

    with pytest.raises(
        TypeError,
        match="roaming_appdata_path must be Path",
    ):
        controller.discover_standard_installations(
            roaming_appdata_path="bad"
        )


def test_invalid_discovery_container_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight_service, _, controller = (
        _controller()
    )

    monkeypatch.setattr(
        preflight_service,
        "discover_standard_installations",
        lambda **kwargs: [],
    )

    with pytest.raises(
        RuntimeError,
        match="invalid discovery result",
    ):
        controller.discover_standard_installations(
            roaming_appdata_path=(
                tmp_path
            )
        )


def test_invalid_discovery_candidate_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight_service, _, controller = (
        _controller()
    )

    monkeypatch.setattr(
        preflight_service,
        "discover_standard_installations",
        lambda **kwargs: (
            object(),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid candidate",
    ):
        controller.discover_standard_installations(
            roaming_appdata_path=(
                tmp_path
            )
        )


def test_run_selected_build_pending(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option(
        tmp_path
    )
    preflight = _preflight_result(
        tmp_path
    )

    (
        preflight_service,
        orchestration_service,
        controller,
    ) = _controller()

    calls = []

    def preflight_call(
        *,
        terminal_path,
        portable,
    ):
        calls.append(
            (
                "preflight",
                terminal_path,
                portable,
            )
        )
        return preflight

    def orchestration_call(
        *,
        preflight_result,
    ):
        calls.append(
            (
                "orchestration",
                preflight_result,
            )
        )

        return (
            CustomerSetupOrchestrationResult(
                status="build_pending",
            )
        )

    monkeypatch.setattr(
        preflight_service,
        "preflight",
        preflight_call,
    )
    monkeypatch.setattr(
        orchestration_service,
        "run",
        orchestration_call,
    )

    result = controller.run_selected(
        option=option
    )

    assert result == (
        CustomerSetupApplicationResult(
            status="build_pending",
            terminal_path=(
                preflight.terminal_path
            ),
            login=LOGIN,
            server=SERVER,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )
    )

    assert calls[0] == (
        "preflight",
        Path(
            option.terminal_path
        ),
        False,
    )

    assert calls[1] == (
        "orchestration",
        preflight,
    )


def test_run_selected_installed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option(
        tmp_path
    )
    preflight = _preflight_result(
        tmp_path
    )

    installation = (
        _installation_result(
            preflight_result=preflight,
            tmp_path=tmp_path,
        )
    )

    (
        preflight_service,
        orchestration_service,
        controller,
    ) = _controller()

    monkeypatch.setattr(
        preflight_service,
        "preflight",
        lambda **kwargs: preflight,
    )

    monkeypatch.setattr(
        orchestration_service,
        "run",
        lambda **kwargs: (
            CustomerSetupOrchestrationResult(
                status="installed",
                installation_result=(
                    installation
                ),
            )
        ),
    )

    result = controller.run_selected(
        option=option
    )

    assert result.status == "installed"
    assert (
        result.terminal_path
        == preflight.terminal_path
    )
    assert result.login == LOGIN
    assert result.server == SERVER
    assert (
        result.account_fingerprint
        == ACCOUNT_FINGERPRINT
    )
    assert (
        result.installed_path
        == installation.installed_path
    )
    assert result.already_present is False


def test_run_selected_requires_option() -> None:
    _, _, controller = _controller()

    with pytest.raises(
        TypeError,
        match="option must be",
    ):
        controller.run_selected(
            option=object()
        )


def test_invalid_preflight_result_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option(
        tmp_path
    )

    preflight_service, _, controller = (
        _controller()
    )

    monkeypatch.setattr(
        preflight_service,
        "preflight",
        lambda **kwargs: object(),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid preflight result",
    ):
        controller.run_selected(
            option=option
        )


def test_invalid_orchestration_result_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option(
        tmp_path
    )
    preflight = _preflight_result(
        tmp_path
    )

    (
        preflight_service,
        orchestration_service,
        controller,
    ) = _controller()

    monkeypatch.setattr(
        preflight_service,
        "preflight",
        lambda **kwargs: preflight,
    )
    monkeypatch.setattr(
        orchestration_service,
        "run",
        lambda **kwargs: object(),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid result",
    ):
        controller.run_selected(
            option=option
        )


@pytest.mark.parametrize(
    (
        "terminal_path",
        "account_fingerprint",
        "match",
    ),
    (
        (
            r"C:\Different\terminal64.exe",
            ACCOUNT_FINGERPRINT,
            "terminal identity",
        ),
        (
            None,
            "Other-Server:999",
            "account identity",
        ),
    ),
)
def test_installed_evidence_must_converge(
    tmp_path: Path,
    monkeypatch,
    terminal_path,
    account_fingerprint,
    match,
) -> None:
    option = _option(
        tmp_path
    )
    preflight = _preflight_result(
        tmp_path
    )

    bad_installation = (
        _installation_result(
            preflight_result=preflight,
            tmp_path=tmp_path,
            terminal_path=(
                preflight.terminal_path
                if terminal_path is None
                else terminal_path
            ),
            account_fingerprint=(
                account_fingerprint
            ),
        )
    )

    (
        preflight_service,
        orchestration_service,
        controller,
    ) = _controller()

    monkeypatch.setattr(
        preflight_service,
        "preflight",
        lambda **kwargs: preflight,
    )
    monkeypatch.setattr(
        orchestration_service,
        "run",
        lambda **kwargs: (
            CustomerSetupOrchestrationResult(
                status="installed",
                installation_result=(
                    bad_installation
                ),
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=match,
    ):
        controller.run_selected(
            option=option
        )


@pytest.mark.parametrize(
    (
        "preflight_service",
        "orchestration_service",
        "match",
    ),
    (
        (
            object(),
            _orchestration_service(),
            "mt5_preflight_service must be",
        ),
        (
            _preflight_service(),
            object(),
            "setup_orchestration_service must be",
        ),
    ),
)
def test_constructor_requires_exact_owners(
    preflight_service,
    orchestration_service,
    match,
) -> None:
    with pytest.raises(
        TypeError,
        match=match,
    ):
        CustomerSetupApplicationController(
            mt5_preflight_service=(
                preflight_service
            ),
            setup_orchestration_service=(
                orchestration_service
            ),
        )


def test_option_normalizes_paths() -> None:
    option = CustomerSetupInstallationOption(
        installation_path="  C:\\MT5  ",
        terminal_path=(
            "  C:\\MT5\\terminal64.exe  "
        ),
        portable=False,
    )

    assert (
        option.installation_path
        == "C:\\MT5"
    )
    assert (
        option.terminal_path
        == "C:\\MT5\\terminal64.exe"
    )


def test_build_pending_result_rejects_installation_fields(
) -> None:
    with pytest.raises(
        ValueError,
        match="build_pending must not contain",
    ):
        CustomerSetupApplicationResult(
            status="build_pending",
            terminal_path=(
                r"C:\MT5\terminal64.exe"
            ),
            login=LOGIN,
            server=SERVER,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
            installed_path=(
                r"C:\MT5\agent.ex5"
            ),
        )


def test_installed_result_requires_installation_fields(
) -> None:
    with pytest.raises(
        (
            TypeError,
            ValueError,
        ),
    ):
        CustomerSetupApplicationResult(
            status="installed",
            terminal_path=(
                r"C:\MT5\terminal64.exe"
            ),
            login=LOGIN,
            server=SERVER,
            account_fingerprint=(
                ACCOUNT_FINGERPRINT
            ),
        )


def test_application_result_does_not_claim_runtime_readiness(
) -> None:
    result = CustomerSetupApplicationResult(
        status="installed",
        terminal_path=(
            r"C:\MT5\terminal64.exe"
        ),
        login=LOGIN,
        server=SERVER,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
        installed_path=(
            r"C:\MT5Data\MQL5\Experts"
            r"\TODOBA_Trusted_Agent.ex5"
        ),
        already_present=False,
    )

    serialized = repr(
        result
    ).lower()

    for forbidden in (
        "agent_running",
        "online",
        "trading_ready",
        "autotrading",
    ):
        assert forbidden not in serialized


def test_owner_has_application_boundary_only(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_application_controller.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_modules: set[str] = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.update(
                alias.name
                for alias in node.names
            )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module is not None:
                imported_modules.add(
                    node.module
                )

    assert "httpx" not in imported_modules
    assert "fastapi" not in imported_modules
    assert "backend.main" not in imported_modules

    forbidden = (
        "tkinter",
        "PySide",
        "PyQt",
        "customtkinter",
        "FileResponse",
        "APIRouter",
        "time.sleep",
        "asyncio.sleep",
        "os.rename",
        "NamedTemporaryFile",
        "initialize_empty(",
        "storage_path",
        "MetaEditor",
    )

    for token in forbidden:
        assert token not in source