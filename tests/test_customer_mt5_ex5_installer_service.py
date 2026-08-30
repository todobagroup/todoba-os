"""
Owner tests for Customer MT5 EX5 Installer Service.
"""

import ast
import hashlib
import os
from pathlib import Path

import pytest

from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallerService,
)
from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)


ARTIFACT = b"TODOBA deployment EX5 test artifact"
ARTIFACT_SHA256 = hashlib.sha256(
    ARTIFACT
).hexdigest()
ARTIFACT_SIZE = len(
    ARTIFACT
)


def _mt5_tree(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
]:
    installation = (
        tmp_path
        / "MT5"
    )
    installation.mkdir()

    terminal = (
        installation
        / "terminal64.exe"
    )
    terminal.write_bytes(
        b"terminal"
    )

    data_path = (
        tmp_path
        / "MT5Data"
    )
    experts_path = (
        data_path
        / "MQL5"
        / "Experts"
    )
    experts_path.mkdir(
        parents=True
    )

    return (
        terminal,
        data_path,
        experts_path,
    )


def _preflight(
    tmp_path: Path,
) -> tuple[
    CustomerMT5SetupPreflightResult,
    Path,
]:
    (
        terminal,
        data_path,
        experts_path,
    ) = _mt5_tree(
        tmp_path
    )

    result = CustomerMT5SetupPreflightResult(
        terminal_path=str(
            terminal.resolve()
        ),
        installation_path=str(
            terminal.parent.resolve()
        ),
        data_path=str(
            data_path.resolve()
        ),
        portable=False,
        login=12345678,
        server="Broker-Server",
        margin_mode=2,
        account_fingerprint=(
            "Broker-Server:12345678"
        ),
    )

    return (
        result,
        experts_path,
    )


def _install(
    service: CustomerMT5EX5InstallerService,
    preflight: CustomerMT5SetupPreflightResult,
):
    return service.install(
        preflight_result=preflight,
        artifact_bytes=ARTIFACT,
        expected_sha256=(
            ARTIFACT_SHA256
        ),
        expected_size_bytes=(
            ARTIFACT_SIZE
        ),
    )


def test_installs_exact_artifact_into_r4_data_path(
    tmp_path: Path,
) -> None:
    preflight, experts_path = _preflight(
        tmp_path
    )

    service = CustomerMT5EX5InstallerService()

    result = _install(
        service,
        preflight,
    )

    target = (
        experts_path
        / "TODOBA_Trusted_Agent.ex5"
    )

    assert target.read_bytes() == ARTIFACT
    assert result.installed_path == str(
        target.resolve()
    )
    assert (
        result.artifact_sha256
        == ARTIFACT_SHA256
    )
    assert (
        result.artifact_size_bytes
        == ARTIFACT_SIZE
    )
    assert result.already_present is False
    assert (
        result.account_fingerprint
        == "Broker-Server:12345678"
    )


def test_same_existing_artifact_is_idempotent(
    tmp_path: Path,
) -> None:
    preflight, experts_path = _preflight(
        tmp_path
    )

    target = (
        experts_path
        / "TODOBA_Trusted_Agent.ex5"
    )
    target.write_bytes(
        ARTIFACT
    )

    original_mtime = target.stat().st_mtime_ns

    result = _install(
        CustomerMT5EX5InstallerService(),
        preflight,
    )

    assert target.read_bytes() == ARTIFACT
    assert target.stat().st_mtime_ns == original_mtime
    assert result.already_present is True


def test_different_existing_artifact_fails_closed(
    tmp_path: Path,
) -> None:
    preflight, experts_path = _preflight(
        tmp_path
    )

    target = (
        experts_path
        / "TODOBA_Trusted_Agent.ex5"
    )
    target.write_bytes(
        b"different deployment"
    )

    original = target.read_bytes()

    with pytest.raises(
        FileExistsError,
        match=(
            "does not match the requested deployment package"
        ),
    ):
        _install(
            CustomerMT5EX5InstallerService(),
            preflight,
        )

    assert target.read_bytes() == original


def test_download_size_mismatch_fails_before_install(
    tmp_path: Path,
) -> None:
    preflight, experts_path = _preflight(
        tmp_path
    )

    service = CustomerMT5EX5InstallerService()

    with pytest.raises(
        ValueError,
        match="artifact size mismatch",
    ):
        service.install(
            preflight_result=preflight,
            artifact_bytes=ARTIFACT,
            expected_sha256=(
                ARTIFACT_SHA256
            ),
            expected_size_bytes=(
                ARTIFACT_SIZE + 1
            ),
        )

    assert not (
        experts_path
        / "TODOBA_Trusted_Agent.ex5"
    ).exists()


def test_download_hash_mismatch_fails_before_install(
    tmp_path: Path,
) -> None:
    preflight, experts_path = _preflight(
        tmp_path
    )

    service = CustomerMT5EX5InstallerService()

    with pytest.raises(
        ValueError,
        match="SHA-256 mismatch",
    ):
        service.install(
            preflight_result=preflight,
            artifact_bytes=ARTIFACT,
            expected_sha256=(
                "0" * 64
            ),
            expected_size_bytes=(
                ARTIFACT_SIZE
            ),
        )

    assert not (
        experts_path
        / "TODOBA_Trusted_Agent.ex5"
    ).exists()


@pytest.mark.parametrize(
    (
        "artifact_bytes",
        "expected_sha256",
        "expected_size",
        "exception_type",
        "match",
    ),
    (
        (
            bytearray(
                ARTIFACT
            ),
            ARTIFACT_SHA256,
            ARTIFACT_SIZE,
            TypeError,
            "artifact_bytes must be bytes",
        ),
        (
            b"",
            ARTIFACT_SHA256,
            ARTIFACT_SIZE,
            ValueError,
            "must not be empty",
        ),
        (
            ARTIFACT,
            "not-a-digest",
            ARTIFACT_SIZE,
            ValueError,
            "expected_sha256 must be",
        ),
        (
            ARTIFACT,
            ARTIFACT_SHA256,
            0,
            ValueError,
            "expected_size_bytes must be",
        ),
    ),
)
def test_rejects_invalid_artifact_contract(
    tmp_path: Path,
    artifact_bytes,
    expected_sha256,
    expected_size,
    exception_type,
    match,
) -> None:
    preflight, _ = _preflight(
        tmp_path
    )

    with pytest.raises(
        exception_type,
        match=match,
    ):
        CustomerMT5EX5InstallerService().install(
            preflight_result=preflight,
            artifact_bytes=artifact_bytes,
            expected_sha256=expected_sha256,
            expected_size_bytes=expected_size,
        )


def test_requires_r4_preflight_result() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "preflight_result must be "
            "CustomerMT5SetupPreflightResult"
        ),
    ):
        CustomerMT5EX5InstallerService().install(
            preflight_result=object(),
            artifact_bytes=ARTIFACT,
            expected_sha256=(
                ARTIFACT_SHA256
            ),
            expected_size_bytes=(
                ARTIFACT_SIZE
            ),
        )


def test_missing_authoritative_data_path_fails_closed(
    tmp_path: Path,
) -> None:
    preflight, _ = _preflight(
        tmp_path
    )

    Path(
        preflight.data_path
    ).rename(
        tmp_path
        / "removed-data"
    )

    with pytest.raises(
        FileNotFoundError,
        match=(
            "Authoritative MT5 data path does not exist"
        ),
    ):
        _install(
            CustomerMT5EX5InstallerService(),
            preflight,
        )


def test_missing_experts_directory_fails_closed(
    tmp_path: Path,
) -> None:
    preflight, experts_path = _preflight(
        tmp_path
    )

    experts_path.rmdir()

    with pytest.raises(
        RuntimeError,
        match="has no Experts directory",
    ):
        _install(
            CustomerMT5EX5InstallerService(),
            preflight,
        )


def test_existing_target_directory_fails_closed(
    tmp_path: Path,
) -> None:
    preflight, experts_path = _preflight(
        tmp_path
    )

    target = (
        experts_path
        / "TODOBA_Trusted_Agent.ex5"
    )
    target.mkdir()

    with pytest.raises(
        RuntimeError,
        match="exists but is not a file",
    ):
        _install(
            CustomerMT5EX5InstallerService(),
            preflight,
        )


def test_install_failure_cleans_temporary_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight, experts_path = _preflight(
        tmp_path
    )

    def fail_rename(
        source,
        destination,
    ):
        del source
        del destination
        raise PermissionError(
            "blocked"
        )

    monkeypatch.setattr(
        os,
        "rename",
        fail_rename,
    )

    with pytest.raises(
        PermissionError,
        match="blocked",
    ):
        _install(
            CustomerMT5EX5InstallerService(),
            preflight,
        )

    assert list(
        experts_path.glob(
            ".TODOBA_Trusted_Agent.*.tmp"
        )
    ) == []


def test_result_means_installed_not_runtime_ready(
    tmp_path: Path,
) -> None:
    preflight, _ = _preflight(
        tmp_path
    )

    result = _install(
        CustomerMT5EX5InstallerService(),
        preflight,
    )

    fields = set(
        result.__dataclass_fields__
    )

    assert "running" not in fields
    assert "online" not in fields
    assert "trading_ready" not in fields
    assert "autotrading" not in fields


def test_owner_has_no_http_runtime_or_build_ownership() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_mt5_ex5_installer_service.py"
    )

    source = path.read_text(
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

    assert "fastapi" not in imported_modules
    assert "backend.main" not in imported_modules

    assert not any(
        module.startswith(
            "backend.trading"
        )
        for module in imported_modules
    )

    forbidden = (
        "MetaTrader5",
        "build_package(",
        "MetaEditor",
        "ChartOpen",
        "ChartApplyTemplate",
        "AutoTrading",
        "TERMINAL_TRADE_ALLOWED",
        "WebRequest",
    )

    for token in forbidden:
        assert token not in source


def test_owner_has_no_duplicate_persistence() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_mt5_ex5_installer_service.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "initialize_empty(",
        "storage_path",
        "json.dump",
        "json.dumps",
    )

    for token in forbidden:
        assert token not in source