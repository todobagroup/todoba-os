from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

INSTALLER = (
    ROOT
    / "scripts"
    / "install_todoba_runtime_release.ps1"
)

SOURCE_RELEASE = (
    Path(r"G:\pt\d3final")
    / "96e9a4dfc6fbbe7e54e68988a3078c3617e3c790"
)

RELEASE_ID = (
    "96e9a4dfc6fbbe7e54e68988a3078c3617e3c790"
)


def _require_installer() -> None:
    assert INSTALLER.is_file(), (
        "Windows runtime release installation owner "
        "does not exist."
    )


def _powershell(
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER),
            *arguments,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _mk_install_root(
    tmp_path: Path,
) -> Path:
    return (
        tmp_path
        / "TODOBA"
    )


def test_release_installer_owner_exists() -> None:
    _require_installer()


def test_validate_only_accepts_verified_release_and_is_non_mutating(
    tmp_path: Path,
) -> None:
    _require_installer()

    install_root = _mk_install_root(
        tmp_path
    )

    result = _powershell(
        "-ReleasePath",
        str(SOURCE_RELEASE),
        "-InstallRoot",
        str(install_root),
        "-ValidateOnly",
    )

    assert result.returncode == 0, (
        result.stdout
        + "\n"
        + result.stderr
    )

    assert (
        "TODOBA_RUNTIME_RELEASE_INSTALL_VALIDATION=PASS"
        in result.stdout
    )

    assert (
        "RELEASE_ID=" + RELEASE_ID
        in result.stdout
    )

    assert "FILESYSTEM_MUTATION=NONE" in result.stdout

    assert not install_root.exists()


def test_installer_rejects_relative_release_path(
    tmp_path: Path,
) -> None:
    _require_installer()

    result = _powershell(
        "-ReleasePath",
        "relative-release",
        "-InstallRoot",
        str(_mk_install_root(tmp_path)),
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "ReleasePath must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_installer_rejects_relative_install_root() -> None:
    _require_installer()

    result = _powershell(
        "-ReleasePath",
        str(SOURCE_RELEASE),
        "-InstallRoot",
        "relative-install-root",
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "InstallRoot must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_installer_rejects_missing_release(
    tmp_path: Path,
) -> None:
    _require_installer()

    missing = (
        tmp_path
        / "missing-release"
    )

    result = _powershell(
        "-ReleasePath",
        str(missing),
        "-InstallRoot",
        str(_mk_install_root(tmp_path)),
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "ReleasePath does not exist."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_installer_requires_release_metadata() -> None:
    _require_installer()

    for name in (
        "VERSION",
        "release-manifest.json",
        "SHA256SUMS",
    ):
        assert (
            SOURCE_RELEASE
            / name
        ).is_file()


def test_install_creates_immutable_versioned_release_and_current_junction(
    tmp_path: Path,
) -> None:
    _require_installer()

    install_root = _mk_install_root(
        tmp_path
    )

    result = _powershell(
        "-ReleasePath",
        str(SOURCE_RELEASE),
        "-InstallRoot",
        str(install_root),
    )

    assert result.returncode == 0, (
        result.stdout
        + "\n"
        + result.stderr
    )

    installed_release = (
        install_root
        / "releases"
        / RELEASE_ID
    )

    current = (
        install_root
        / "current"
    )

    assert installed_release.is_dir()
    assert current.exists()
    assert current.is_dir()

    assert (
        installed_release
        / "VERSION"
    ).read_text(
        encoding="utf-8-sig"
    ).strip() == RELEASE_ID

    assert (
        current
        / "VERSION"
    ).read_text(
        encoding="utf-8-sig"
    ).strip() == RELEASE_ID

    attributes = os.stat(
        current,
        follow_symlinks=False,
    ).st_file_attributes

    assert (
        attributes
        & 0x400
    ), "current must be a Windows reparse-point junction"


def test_installed_release_matches_source_manifest_hashes(
    tmp_path: Path,
) -> None:
    _require_installer()

    install_root = _mk_install_root(
        tmp_path
    )

    result = _powershell(
        "-ReleasePath",
        str(SOURCE_RELEASE),
        "-InstallRoot",
        str(install_root),
    )

    assert result.returncode == 0

    installed_release = (
        install_root
        / "releases"
        / RELEASE_ID
    )

    source_manifest = json.loads(
        (
            SOURCE_RELEASE
            / "release-manifest.json"
        ).read_text(
            encoding="utf-8-sig"
        )
    )

    installed_manifest = json.loads(
        (
            installed_release
            / "release-manifest.json"
        ).read_text(
            encoding="utf-8-sig"
        )
    )

    assert installed_manifest == source_manifest


def test_existing_versioned_release_is_fail_closed(
    tmp_path: Path,
) -> None:
    _require_installer()

    install_root = _mk_install_root(
        tmp_path
    )

    first = _powershell(
        "-ReleasePath",
        str(SOURCE_RELEASE),
        "-InstallRoot",
        str(install_root),
    )

    assert first.returncode == 0

    second = _powershell(
        "-ReleasePath",
        str(SOURCE_RELEASE),
        "-InstallRoot",
        str(install_root),
    )

    assert second.returncode != 0

    assert (
        "Versioned release already exists."
        in (
            second.stdout
            + second.stderr
        )
    )


def test_installer_does_not_own_runtime_or_task_authority() -> None:
    _require_installer()

    text = INSTALLER.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "Register-ScheduledTask",
        "Set-ScheduledTask",
        "Start-ScheduledTask",
        "Stop-ScheduledTask",
        "Start-Process",
        "Stop-Process",
        "SetEnvironmentVariable",
    )

    for fragment in forbidden:
        assert fragment not in text
