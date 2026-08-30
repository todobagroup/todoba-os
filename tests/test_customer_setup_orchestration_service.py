"""
Owner tests for Customer Setup Orchestration Service.
"""

import ast
import hashlib
from pathlib import Path

import pytest

from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallationResult,
    CustomerMT5EX5InstallerService,
)
from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)
from backend.commercial.customer_setup_http_client import (
    CustomerSetupHttpClient,
    CustomerSetupProvisioningTransportResult,
)
from backend.commercial.customer_setup_orchestration_service import (
    CustomerSetupOrchestrationResult,
    CustomerSetupOrchestrationService,
)


ARTIFACT_BYTES = b"TODOBA deployment-specific EX5"
ARTIFACT_SHA256 = hashlib.sha256(
    ARTIFACT_BYTES
).hexdigest()
ARTIFACT_SIZE_BYTES = len(
    ARTIFACT_BYTES
)
LOGIN = 12345678
SERVER = "Broker-Server"
ACCOUNT_FINGERPRINT = (
    f"{SERVER}:{LOGIN}"
)


def _preflight_result(
    tmp_path: Path,
) -> CustomerMT5SetupPreflightResult:
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
    account_fingerprint: str = ACCOUNT_FINGERPRINT,
    terminal_path: str | None = None,
    artifact_sha256: str = ARTIFACT_SHA256,
    artifact_size_bytes: int = ARTIFACT_SIZE_BYTES,
) -> CustomerMT5EX5InstallationResult:
    installed_path = (
        tmp_path
        / "TODOBA_Trusted_Agent.ex5"
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
            installed_path
        ),
        artifact_sha256=(
            artifact_sha256
        ),
        artifact_size_bytes=(
            artifact_size_bytes
        ),
        already_present=False,
    )


def _owners():
    client = CustomerSetupHttpClient(
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

    service = (
        CustomerSetupOrchestrationService(
            setup_http_client=client,
            ex5_installer_service=installer,
        )
    )

    return (
        client,
        installer,
        service,
    )


def test_build_pending_stops_before_download_and_install(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight = _preflight_result(
        tmp_path
    )

    client, installer, service = (
        _owners()
    )

    calls = []

    def provision(
        *,
        account_fingerprint,
    ):
        calls.append(
            (
                "provision",
                account_fingerprint,
            )
        )

        return (
            CustomerSetupProvisioningTransportResult(
                status="build_pending",
            )
        )

    def forbidden_download():
        raise AssertionError(
            "download must not run while build is pending"
        )

    def forbidden_install(
        **kwargs,
    ):
        del kwargs
        raise AssertionError(
            "install must not run while build is pending"
        )

    monkeypatch.setattr(
        client,
        "provision",
        provision,
    )
    monkeypatch.setattr(
        client,
        "download_package",
        forbidden_download,
    )
    monkeypatch.setattr(
        installer,
        "install",
        forbidden_install,
    )

    result = service.run(
        preflight_result=preflight
    )

    assert result == (
        CustomerSetupOrchestrationResult(
            status="build_pending",
        )
    )

    assert calls == [
        (
            "provision",
            ACCOUNT_FINGERPRINT,
        )
    ]


def test_ready_downloads_then_installs_exact_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight = _preflight_result(
        tmp_path
    )

    client, installer, service = (
        _owners()
    )

    calls = []

    def provision(
        *,
        account_fingerprint,
    ):
        calls.append(
            (
                "provision",
                account_fingerprint,
            )
        )

        return (
            CustomerSetupProvisioningTransportResult(
                status="ready",
                artifact_sha256=(
                    ARTIFACT_SHA256
                ),
                artifact_size_bytes=(
                    ARTIFACT_SIZE_BYTES
                ),
            )
        )

    def download_package():
        calls.append(
            (
                "download",
                None,
            )
        )
        return ARTIFACT_BYTES

    expected_installation = (
        _installation_result(
            preflight_result=preflight,
            tmp_path=tmp_path,
        )
    )

    def install(
        **kwargs,
    ):
        calls.append(
            (
                "install",
                kwargs,
            )
        )
        return expected_installation

    monkeypatch.setattr(
        client,
        "provision",
        provision,
    )
    monkeypatch.setattr(
        client,
        "download_package",
        download_package,
    )
    monkeypatch.setattr(
        installer,
        "install",
        install,
    )

    result = service.run(
        preflight_result=preflight
    )

    assert result.status == "installed"
    assert (
        result.installation_result
        == expected_installation
    )

    assert calls[0] == (
        "provision",
        ACCOUNT_FINGERPRINT,
    )
    assert calls[1] == (
        "download",
        None,
    )

    install_kwargs = calls[2][1]

    assert (
        install_kwargs["preflight_result"]
        is preflight
    )
    assert (
        install_kwargs["artifact_bytes"]
        == ARTIFACT_BYTES
    )
    assert (
        install_kwargs["expected_sha256"]
        == ARTIFACT_SHA256
    )
    assert (
        install_kwargs[
            "expected_size_bytes"
        ]
        == ARTIFACT_SIZE_BYTES
    )


def test_run_requires_authoritative_preflight_result(
) -> None:
    _, _, service = _owners()

    with pytest.raises(
        TypeError,
        match="preflight_result must be",
    ):
        service.run(
            preflight_result=object()
        )


@pytest.mark.parametrize(
    (
        "http_client",
        "installer",
        "match",
    ),
    (
        (
            object(),
            CustomerMT5EX5InstallerService(),
            "setup_http_client must be",
        ),
        (
            CustomerSetupHttpClient(
                setup_base_url="https://example.com",
                setup_handoff_credential="secret",
            ),
            object(),
            "ex5_installer_service must be",
        ),
    ),
)
def test_constructor_requires_exact_owner_types(
    http_client,
    installer,
    match,
) -> None:
    with pytest.raises(
        TypeError,
        match=match,
    ):
        CustomerSetupOrchestrationService(
            setup_http_client=http_client,
            ex5_installer_service=installer,
        )


def test_invalid_provisioning_result_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight = _preflight_result(
        tmp_path
    )
    client, _, service = _owners()

    monkeypatch.setattr(
        client,
        "provision",
        lambda **kwargs: object(),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid provisioning result",
    ):
        service.run(
            preflight_result=preflight
        )


def test_invalid_download_result_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight = _preflight_result(
        tmp_path
    )
    client, _, service = _owners()

    monkeypatch.setattr(
        client,
        "provision",
        lambda **kwargs: (
            CustomerSetupProvisioningTransportResult(
                status="ready",
                artifact_sha256=(
                    ARTIFACT_SHA256
                ),
                artifact_size_bytes=(
                    ARTIFACT_SIZE_BYTES
                ),
            )
        ),
    )

    monkeypatch.setattr(
        client,
        "download_package",
        lambda: bytearray(
            ARTIFACT_BYTES
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="invalid package bytes",
    ):
        service.run(
            preflight_result=preflight
        )


def test_invalid_installer_result_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight = _preflight_result(
        tmp_path
    )
    client, installer, service = (
        _owners()
    )

    monkeypatch.setattr(
        client,
        "provision",
        lambda **kwargs: (
            CustomerSetupProvisioningTransportResult(
                status="ready",
                artifact_sha256=(
                    ARTIFACT_SHA256
                ),
                artifact_size_bytes=(
                    ARTIFACT_SIZE_BYTES
                ),
            )
        ),
    )
    monkeypatch.setattr(
        client,
        "download_package",
        lambda: ARTIFACT_BYTES,
    )
    monkeypatch.setattr(
        installer,
        "install",
        lambda **kwargs: object(),
    )

    with pytest.raises(
        RuntimeError,
        match="installer returned invalid result",
    ):
        service.run(
            preflight_result=preflight
        )


@pytest.mark.parametrize(
    (
        "field",
        "replacement",
        "match",
    ),
    (
        (
            "account_fingerprint",
            "Other-Server:999",
            "account identity",
        ),
        (
            "terminal_path",
            "C:\\different\\terminal64.exe",
            "terminal does not match",
        ),
        (
            "artifact_sha256",
            "b" * 64,
            "SHA-256 does not match",
        ),
        (
            "artifact_size_bytes",
            ARTIFACT_SIZE_BYTES + 1,
            "size does not match",
        ),
    ),
)
def test_installer_result_must_converge_with_authorities(
    tmp_path: Path,
    monkeypatch,
    field,
    replacement,
    match,
) -> None:
    preflight = _preflight_result(
        tmp_path
    )
    client, installer, service = (
        _owners()
    )

    monkeypatch.setattr(
        client,
        "provision",
        lambda **kwargs: (
            CustomerSetupProvisioningTransportResult(
                status="ready",
                artifact_sha256=(
                    ARTIFACT_SHA256
                ),
                artifact_size_bytes=(
                    ARTIFACT_SIZE_BYTES
                ),
            )
        ),
    )
    monkeypatch.setattr(
        client,
        "download_package",
        lambda: ARTIFACT_BYTES,
    )

    values = {
        "account_fingerprint": (
            ACCOUNT_FINGERPRINT
        ),
        "terminal_path": (
            preflight.terminal_path
        ),
        "artifact_sha256": (
            ARTIFACT_SHA256
        ),
        "artifact_size_bytes": (
            ARTIFACT_SIZE_BYTES
        ),
    }
    values[field] = replacement

    bad_result = _installation_result(
        preflight_result=preflight,
        tmp_path=tmp_path,
        account_fingerprint=(
            values["account_fingerprint"]
        ),
        terminal_path=(
            values["terminal_path"]
        ),
        artifact_sha256=(
            values["artifact_sha256"]
        ),
        artifact_size_bytes=(
            values["artifact_size_bytes"]
        ),
    )

    monkeypatch.setattr(
        installer,
        "install",
        lambda **kwargs: bad_result,
    )

    with pytest.raises(
        RuntimeError,
        match=match,
    ):
        service.run(
            preflight_result=preflight
        )


def test_build_pending_result_rejects_installation(
    tmp_path: Path,
) -> None:
    preflight = _preflight_result(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match=(
            "build_pending must not contain "
            "installation result"
        ),
    ):
        CustomerSetupOrchestrationResult(
            status="build_pending",
            installation_result=(
                _installation_result(
                    preflight_result=preflight,
                    tmp_path=tmp_path,
                )
            ),
        )


def test_installed_result_requires_installation_result(
) -> None:
    with pytest.raises(
        ValueError,
        match="installed requires",
    ):
        CustomerSetupOrchestrationResult(
            status="installed",
        )


def test_orchestration_result_does_not_claim_runtime_ready(
    tmp_path: Path,
) -> None:
    preflight = _preflight_result(
        tmp_path
    )

    result = (
        CustomerSetupOrchestrationResult(
            status="installed",
            installation_result=(
                _installation_result(
                    preflight_result=preflight,
                    tmp_path=tmp_path,
                )
            ),
        )
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


def test_owner_has_only_orchestration_ownership(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_orchestration_service.py"
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
        "CustomerMT5SetupPreflightService",
        "time.sleep",
        "asyncio.sleep",
        "MetaTrader5",
        "FileResponse",
        "APIRouter",
        "initialize_empty(",
        "storage_path",
        "os.rename",
        "NamedTemporaryFile",
    )

    for token in forbidden:
        assert token not in source