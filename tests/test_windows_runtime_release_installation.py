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


def test_additional_release_requires_explicit_installer_mode() -> None:
    """Additional installation must be explicitly selected."""
    _require_installer()

    installer = INSTALLER.read_text(
        encoding="utf-8-sig",
    )

    assert "[switch]$AdditionalRelease" in installer, (
        "Additional release installation mode is missing"
    )


ADDITIONAL_SOURCE_RELEASE = (
    Path(r"G:\TODOBA OS\TODOBA Runtime Releases CAP-R3")
    / "502cffe1f0e6eee0205ee0f2e93233324a336b31"
)

ADDITIONAL_RELEASE_ID = (
    "502cffe1f0e6eee0205ee0f2e93233324a336b31"
)


def test_additional_release_validate_only_preserves_current(
    tmp_path: Path,
) -> None:
    """ValidateOnly accepts B without changing installation A."""
    install_root = _mk_install_root(tmp_path)

    initial = _powershell(
        "-ReleasePath", str(SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    current = install_root / "current"
    current_before = os.path.realpath(current)
    new_release = install_root / "releases" / ADDITIONAL_RELEASE_ID

    assert current.is_dir()
    assert not new_release.exists()

    validation = _powershell(
        "-ReleasePath", str(ADDITIONAL_SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
        "-AdditionalRelease",
        "-ValidateOnly",
    )

    assert validation.returncode == 0, (
        validation.stdout + "\n" + validation.stderr
    )
    assert "FILESYSTEM_MUTATION=NONE" in validation.stdout
    assert not new_release.exists()
    assert os.path.realpath(current) == current_before
    assert (current / "VERSION").read_text(
        encoding="utf-8-sig",
    ).strip() == RELEASE_ID


def test_additional_release_installs_without_switching_current(
    tmp_path: Path,
) -> None:
    """Install B immutably; A remains current; duplicate B fails."""
    install_root = _mk_install_root(tmp_path)

    initial = _powershell(
        "-ReleasePath", str(SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    current = install_root / "current"
    current_before = os.path.realpath(current)
    new_release = install_root / "releases" / ADDITIONAL_RELEASE_ID

    additional = _powershell(
        "-ReleasePath", str(ADDITIONAL_SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
        "-AdditionalRelease",
    )

    assert additional.returncode == 0, (
        additional.stdout + "\n" + additional.stderr
    )
    assert new_release.is_dir()
    assert (new_release / "VERSION").read_text(
        encoding="utf-8-sig",
    ).strip() == ADDITIONAL_RELEASE_ID
    assert os.path.realpath(current) == current_before
    assert (current / "VERSION").read_text(
        encoding="utf-8-sig",
    ).strip() == RELEASE_ID

    duplicate = _powershell(
        "-ReleasePath", str(ADDITIONAL_SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
        "-AdditionalRelease",
    )

    assert duplicate.returncode != 0
    assert "Versioned release already exists." in (
        duplicate.stdout + duplicate.stderr
    )
    assert os.path.realpath(current) == current_before



def test_additional_release_refuses_missing_current(
    tmp_path: Path,
) -> None:
    """Additional mode cannot bootstrap a new installation."""
    install_root = _mk_install_root(tmp_path)

    result = _powershell(
        "-ReleasePath", str(ADDITIONAL_SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
        "-AdditionalRelease",
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert not install_root.exists()


def test_additional_release_refuses_nonjunction_current(
    tmp_path: Path,
) -> None:
    """A normal directory cannot impersonate current."""
    install_root = _mk_install_root(tmp_path)
    current = install_root / "current"
    current.mkdir(parents=True)

    result = _powershell(
        "-ReleasePath", str(ADDITIONAL_SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
        "-AdditionalRelease",
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert current.is_dir()
    assert not (
        install_root / "releases" / ADDITIONAL_RELEASE_ID
    ).exists()


def test_additional_release_refuses_corrupted_current_release(
    tmp_path: Path,
) -> None:
    """Corrupted current release cannot authorize new publication."""
    install_root = _mk_install_root(tmp_path)

    initial = _powershell(
        "-ReleasePath", str(SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    current = install_root / "current"
    before_target = os.path.realpath(current)

    # Mutate only the isolated test installation, never the source.
    installed_version = (
        install_root / "releases" / RELEASE_ID / "VERSION"
    )
    installed_version.write_text(
        "0" * 40 + "\n",
        encoding="utf-8",
    )

    result = _powershell(
        "-ReleasePath", str(ADDITIONAL_SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
        "-AdditionalRelease",
        "-ValidateOnly",
    )

    assert result.returncode != 0
    assert os.path.realpath(current) == before_target
    assert not (
        install_root / "releases" / ADDITIONAL_RELEASE_ID
    ).exists()



def test_additional_release_reports_post_publication_failure(
    tmp_path: Path,
) -> None:
    """A published but incomplete install must report recoverable failure."""
    install_root = _mk_install_root(tmp_path)

    initial = _powershell(
        "-ReleasePath", str(SOURCE_RELEASE),
        "-InstallRoot", str(install_root),
    )
    assert initial.returncode == 0, initial.stdout + initial.stderr

    current = install_root / "current"
    original_target = os.path.realpath(current)

    # Inject only into an isolated test copy, never production source.
    source_text = INSTALLER.read_text(encoding="utf-8-sig")
    injection_anchor = "    $published = $true"

    assert source_text.count(injection_anchor) == 1

    injected_text = source_text.replace(
        injection_anchor,
        injection_anchor + '\n    throw "INJECTED_POST_PUBLICATION_FAILURE"',
        1,
    )

    injected_installer = tmp_path / "injected_installer.ps1"
    injected_installer.write_text(
        injected_text,
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", str(injected_installer),
            "-ReleasePath", str(ADDITIONAL_SOURCE_RELEASE),
            "-InstallRoot", str(install_root),
            "-AdditionalRelease",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    combined = result.stdout + "\n" + result.stderr
    new_release = install_root / "releases" / ADDITIONAL_RELEASE_ID

    assert result.returncode != 0
    assert "INJECTED_POST_PUBLICATION_FAILURE" in combined
    assert new_release.is_dir()
    assert (
        new_release / "VERSION"
    ).read_text(encoding="utf-8-sig").strip() == ADDITIONAL_RELEASE_ID

    assert os.path.realpath(current) == original_target
    assert (
        current / "VERSION"
    ).read_text(encoding="utf-8-sig").strip() == RELEASE_ID

    assert "CURRENT_UNCHANGED=TRUE" not in result.stdout
    assert "TODOBA_RUNTIME_RELEASE_INSTALLED=TRUE" not in result.stdout

    assert (
        "TODOBA_ADDITIONAL_RELEASE_POST_PUBLISH_FAILURE=TRUE"
        in result.stdout
    ), "Post-publication recovery status is not reported"

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
