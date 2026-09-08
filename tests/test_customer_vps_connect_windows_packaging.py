from pathlib import Path
import sys

import pytest

import scripts.build_customer_vps_connect_windows as build_owner


PRODUCT_NAME = "TODOBA VPS Connect"
VALIDATED_PYINSTALLER_VERSION = "6.22.2"


def test_product_identity_is_locked():
    assert build_owner._PRODUCT_NAME == PRODUCT_NAME

    assert (
        build_owner._VALIDATED_PYINSTALLER_VERSION
        == VALIDATED_PYINSTALLER_VERSION
    )


def test_entrypoint_is_vps_connect_production_entrypoint():
    path = build_owner._entrypoint_path()

    assert path.name == "customer_vps_connect.py"

    assert (
        path.parent.name
        == "scripts"
    )

    assert path.is_absolute()


def test_icon_is_existing_todoba_trading_icon():
    path = build_owner._icon_path()

    assert path.name == "TODOBA_Trading.ico"

    assert (
        path.parent.name
        == "assets"
    )

    assert path.is_absolute()


def test_build_artifacts_are_outside_repository():
    repository_root = (
        build_owner._repository_root()
    )

    build_root = (
        build_owner._build_root()
    )

    dist_root = (
        build_owner._dist_root()
    )

    assert repository_root not in (
        build_root.parents
    )

    assert repository_root not in (
        dist_root.parents
    )

    assert build_root != repository_root
    assert dist_root != repository_root


def test_build_command_targets_windowed_onedir_vps_connect():
    command = build_owner._build_command()

    assert command[0] == sys.executable
    assert command[1:3] == (
        "-m",
        "PyInstaller",
    )

    assert "--noconfirm" in command
    assert "--clean" in command
    assert "--onedir" in command
    assert "--windowed" in command

    name_index = command.index(
        "--name"
    )

    assert (
        command[name_index + 1]
        == PRODUCT_NAME
    )

    icon_index = command.index(
        "--icon"
    )

    assert (
        Path(command[icon_index + 1])
        == build_owner._icon_path()
    )

    paths_index = command.index(
        "--paths"
    )

    assert (
        Path(command[paths_index + 1])
        == build_owner._repository_root()
    )

    assert (
        str(build_owner._entrypoint_path())
        == command[-1]
    )


def test_build_command_collects_metatrader5_package():
    command = build_owner._build_command()

    indexes = [
        index
        for index, value in enumerate(command)
        if value == "--collect-all"
    ]

    packages = {
        command[index + 1]
        for index in indexes
    }

    assert "MetaTrader5" in packages


def test_validate_build_environment_rejects_wrong_pyinstaller(
    monkeypatch,
):
    monkeypatch.setattr(
        build_owner,
        "_read_pyinstaller_version",
        lambda: "0.0.0",
    )

    with pytest.raises(RuntimeError):
        build_owner._validate_build_environment()


def test_validate_build_environment_accepts_locked_toolchain(
    monkeypatch,
):
    monkeypatch.setattr(
        build_owner,
        "_read_pyinstaller_version",
        lambda: VALIDATED_PYINSTALLER_VERSION,
    )

    monkeypatch.setattr(
        build_owner,
        "_entrypoint_path",
        lambda: Path(__file__),
    )

    monkeypatch.setattr(
        build_owner,
        "_icon_path",
        lambda: Path(__file__),
    )

    build_owner._validate_build_environment()


def test_build_invokes_pyinstaller_once_and_returns_exact_exe(
    monkeypatch,
    tmp_path,
):
    calls = []

    monkeypatch.setattr(
        build_owner,
        "_validate_build_environment",
        lambda: None,
    )

    monkeypatch.setattr(
        build_owner,
        "_build_root",
        lambda: tmp_path / "build",
    )

    monkeypatch.setattr(
        build_owner,
        "_dist_root",
        lambda: tmp_path / "dist",
    )

    fake_command = (
        "python",
        "-m",
        "PyInstaller",
    )

    monkeypatch.setattr(
        build_owner,
        "_build_command",
        lambda: fake_command,
    )

    class Completed:
        returncode = 0

    def fake_run(
        command,
        *,
        check,
        cwd,
    ):
        calls.append(
            (
                command,
                check,
                cwd,
            )
        )

        exe = (
            tmp_path
            / "dist"
            / PRODUCT_NAME
            / f"{PRODUCT_NAME}.exe"
        )

        exe.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        exe.write_bytes(
            b"exe"
        )

        return Completed()

    monkeypatch.setattr(
        build_owner.subprocess,
        "run",
        fake_run,
    )

    result = (
        build_owner
        .build_customer_vps_connect_windows_executable()
    )

    assert len(calls) == 1

    command, check, cwd = calls[0]

    assert command == fake_command
    assert check is True

    assert (
        cwd
        == build_owner._repository_root()
    )

    assert (
        result.name
        == f"{PRODUCT_NAME}.exe"
    )

    assert result.is_file()


def test_build_owner_has_packaging_authority_only():
    source = Path(
        "scripts/"
        "build_customer_vps_connect_windows.py"
    ).read_text(
        encoding="utf-8-sig",
    )

    for forbidden in (
        "CustomerVPSConnectLauncher",
        "CustomerVPSConnectGuiShell",
        "CustomerVPSConnectApplicationShell",
        "CustomerVPSConnectCoreOrchestrationService",
        "CustomerVPSConnectGrantHttpClient",
        "CustomerVPSConnectLiveProofHttpClient",
        "BrokerStateStore",
        "initialize_empty",
        "APPDATA",
        "TODOBA_CLOUD_BASE_URL",
        "activation_code",
        "grant_credential",
        "account_fingerprint",
        "terminate(",
        "kill(",
    ):
        assert forbidden not in source