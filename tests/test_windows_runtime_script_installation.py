from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

INSTALLER = (
    ROOT
    / "scripts"
    / "install_todoba_runtime_scripts.ps1"
)

SOURCE_LAUNCHER = (
    ROOT
    / "scripts"
    / "start_todoba.ps1"
)

SOURCE_CONTROLLER = (
    ROOT
    / "scripts"
    / "control_todoba.ps1"
)


def _require_installer() -> None:
    assert INSTALLER.is_file(), (
        "Stable runtime script installer does not exist."
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest().upper()


def _make_source_release(
    tmp_path: Path,
) -> Path:
    release = (
        tmp_path
        / "release"
    )

    scripts = (
        release
        / "scripts"
    )

    scripts.mkdir(
        parents=True
    )

    (
        scripts
        / "start_todoba.ps1"
    ).write_bytes(
        SOURCE_LAUNCHER.read_bytes()
    )

    (
        scripts
        / "control_todoba.ps1"
    ).write_bytes(
        SOURCE_CONTROLLER.read_bytes()
    )

    return release


def test_runtime_script_installer_exists() -> None:
    _require_installer()


def test_validate_only_accepts_explicit_release_and_runtime_roots(
    tmp_path: Path,
) -> None:
    _require_installer()

    source_release = (
        _make_source_release(
            tmp_path
        )
    )

    runtime_root = (
        tmp_path
        / "stable-runtime"
    )

    result = _powershell(
        "-SourceReleaseRoot",
        str(source_release),
        "-RuntimeRoot",
        str(runtime_root),
        "-ValidateOnly",
    )

    assert result.returncode == 0, (
        result.stdout
        + "\n"
        + result.stderr
    )

    output = result.stdout

    assert (
        "TODOBA_RUNTIME_SCRIPT_INSTALLATION_VALIDATION=PASS"
        in output
    )

    assert (
        "SCRIPT_COUNT=2"
        in output
    )

    assert (
        "FILESYSTEM_MUTATION=NONE"
        in output
    )

    assert not runtime_root.exists()


def test_rejects_relative_source_release_root(
    tmp_path: Path,
) -> None:
    _require_installer()

    result = _powershell(
        "-SourceReleaseRoot",
        "relative-release",
        "-RuntimeRoot",
        str(tmp_path / "runtime"),
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "SourceReleaseRoot must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_relative_runtime_root(
    tmp_path: Path,
) -> None:
    _require_installer()

    source_release = (
        _make_source_release(
            tmp_path
        )
    )

    result = _powershell(
        "-SourceReleaseRoot",
        str(source_release),
        "-RuntimeRoot",
        "relative-runtime",
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "RuntimeRoot must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_missing_source_release(
    tmp_path: Path,
) -> None:
    _require_installer()

    result = _powershell(
        "-SourceReleaseRoot",
        str(
            tmp_path
            / "missing-release"
        ),
        "-RuntimeRoot",
        str(tmp_path / "runtime"),
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "SourceReleaseRoot does not exist."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_source_missing_launcher(
    tmp_path: Path,
) -> None:
    _require_installer()

    source_release = (
        _make_source_release(
            tmp_path
        )
    )

    (
        source_release
        / "scripts"
        / "start_todoba.ps1"
    ).unlink()

    result = _powershell(
        "-SourceReleaseRoot",
        str(source_release),
        "-RuntimeRoot",
        str(tmp_path / "runtime"),
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "Source runtime launcher does not exist."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_source_missing_controller(
    tmp_path: Path,
) -> None:
    _require_installer()

    source_release = (
        _make_source_release(
            tmp_path
        )
    )

    (
        source_release
        / "scripts"
        / "control_todoba.ps1"
    ).unlink()

    result = _powershell(
        "-SourceReleaseRoot",
        str(source_release),
        "-RuntimeRoot",
        str(tmp_path / "runtime"),
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "Source runtime controller does not exist."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_install_creates_exact_stable_runtime_pair(
    tmp_path: Path,
) -> None:
    _require_installer()

    source_release = (
        _make_source_release(
            tmp_path
        )
    )

    runtime_root = (
        tmp_path
        / "stable-runtime"
    )

    result = _powershell(
        "-SourceReleaseRoot",
        str(source_release),
        "-RuntimeRoot",
        str(runtime_root),
    )

    assert result.returncode == 0, (
        result.stdout
        + "\n"
        + result.stderr
    )

    launcher = (
        runtime_root
        / "start_todoba.ps1"
    )

    controller = (
        runtime_root
        / "control_todoba.ps1"
    )

    assert launcher.is_file()
    assert controller.is_file()

    assert {
        path.name
        for path in runtime_root.iterdir()
    } == {
        "start_todoba.ps1",
        "control_todoba.ps1",
    }

    assert (
        _sha256(launcher)
        == _sha256(
            source_release
            / "scripts"
            / "start_todoba.ps1"
        )
    )

    assert (
        _sha256(controller)
        == _sha256(
            source_release
            / "scripts"
            / "control_todoba.ps1"
        )
    )

    assert (
        "TODOBA_RUNTIME_SCRIPTS_INSTALLED=TRUE"
        in result.stdout
    )


def test_existing_runtime_root_fails_closed(
    tmp_path: Path,
) -> None:
    _require_installer()

    source_release = (
        _make_source_release(
            tmp_path
        )
    )

    runtime_root = (
        tmp_path
        / "stable-runtime"
    )

    runtime_root.mkdir()

    existing = (
        runtime_root
        / "sentinel.txt"
    )

    existing.write_text(
        "preserve",
        encoding="utf-8",
    )

    result = _powershell(
        "-SourceReleaseRoot",
        str(source_release),
        "-RuntimeRoot",
        str(runtime_root),
    )

    assert result.returncode != 0

    assert (
        "RuntimeRoot already exists."
        in (
            result.stdout
            + result.stderr
        )
    )

    assert existing.read_text(
        encoding="utf-8"
    ) == "preserve"


def test_controller_and_launcher_remain_adjacent() -> None:
    assert SOURCE_CONTROLLER.is_file()
    assert SOURCE_LAUNCHER.is_file()

    controller = SOURCE_CONTROLLER.read_text(
        encoding="utf-8-sig"
    )

    assert "$PSScriptRoot" in controller
    assert "start_todoba.ps1" in controller


def test_installer_does_not_own_other_runtime_authorities() -> None:
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
        "TODOBA_RELEASE_ROOT",
        "TODOBA_PYTHON_EXECUTABLE",
        "TODOBA_ENV_FILE",
        "TELEGRAM_SESSION",
        "TODOBA_RUNTIME_LOG_ROOT",
        "ItemType Junction",
        "New-Item -ItemType Junction",
        "Move-Item",
    )

    for fragment in forbidden:
        assert fragment not in text
