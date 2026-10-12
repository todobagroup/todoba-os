from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SWITCHER = (
    ROOT
    / "scripts"
    / "switch_todoba_runtime_release.ps1"
)

RELEASE_A = "a" * 40
RELEASE_B = "b" * 40


def _require_switcher() -> None:
    assert SWITCHER.is_file(), (
        "Controlled runtime release switcher does not exist."
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
            str(SWITCHER),
            *arguments,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def _make_valid_release(
    releases_root: Path,
    release_id: str,
) -> Path:
    release = (
        releases_root
        / release_id
    )

    release.mkdir(
        parents=True,
        exist_ok=False,
    )

    payload = (
        "release="
        + release_id
        + "\n"
    ).encode("utf-8")

    (
        release
        / "payload.txt"
    ).write_bytes(payload)

    version_payload = (
        release_id
        + "\n"
    ).encode("utf-8")

    (
        release
        / "VERSION"
    ).write_bytes(
        version_payload
    )

    entries = []

    for relative_path in (
        "VERSION",
        "payload.txt",
    ):
        path = (
            release
            / relative_path
        )

        data = path.read_bytes()

        entries.append(
            {
                "path": relative_path,
                "sha256": _sha256_bytes(data),
                "size": len(data),
            }
        )

    entries = sorted(
        entries,
        key=lambda item: item["path"],
    )

    manifest = {
        "schema_version": 1,
        "release_id": release_id,
        "files": entries,
    }

    (
        release
        / "release-manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    (
        release
        / "SHA256SUMS"
    ).write_text(
        "".join(
            (
                entry["sha256"]
                + "  "
                + entry["path"]
                + "\n"
            )
            for entry in entries
        ),
        encoding="utf-8",
        newline="\n",
    )

    return release


def _make_install_root(
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    install_root = (
        tmp_path
        / "todoba"
    )

    releases_root = (
        install_root
        / "releases"
    )

    releases_root.mkdir(
        parents=True
    )

    release_a = _make_valid_release(
        releases_root,
        RELEASE_A,
    )

    release_b = _make_valid_release(
        releases_root,
        RELEASE_B,
    )

    return (
        install_root,
        release_a,
        release_b,
    )


def _powershell_single_quote(
    value: str,
) -> str:
    return (
        "'"
        + value.replace(
            "'",
            "''",
        )
        + "'"
    )


def _make_junction(
    current: Path,
    target: Path,
) -> None:
    current_literal = (
        _powershell_single_quote(
            str(current)
        )
    )

    target_literal = (
        _powershell_single_quote(
            str(target)
        )
    )

    command = (
        "New-Item "
        "-ItemType Junction "
        "-Path "
        + current_literal
        + " "
        "-Target "
        + target_literal
        + " "
        "-ErrorAction Stop "
        "| Out-Null"
    )

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, (
        completed.stdout
        + "\n"
        + completed.stderr
    )


def _current_release_id(
    install_root: Path,
) -> str:
    return (
        install_root
        / "current"
        / "VERSION"
    ).read_text(
        encoding="utf-8-sig"
    ).strip()


def test_runtime_release_switcher_exists() -> None:
    _require_switcher()


def test_validate_only_accepts_valid_installed_target(
    tmp_path: Path,
) -> None:
    _require_switcher()

    (
        install_root,
        release_a,
        _,
    ) = _make_install_root(
        tmp_path
    )

    current = (
        install_root
        / "current"
    )

    _make_junction(
        current,
        release_a,
    )

    result = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        RELEASE_B,
        "-ValidateOnly",
    )

    assert result.returncode == 0, (
        result.stdout
        + "\n"
        + result.stderr
    )

    assert (
        "TODOBA_RUNTIME_RELEASE_SWITCH_VALIDATION=PASS"
        in result.stdout
    )

    assert (
        "CURRENT_RELEASE_ID="
        + RELEASE_A
        in result.stdout
    )

    assert (
        "TARGET_RELEASE_ID="
        + RELEASE_B
        in result.stdout
    )

    assert (
        "FILESYSTEM_MUTATION=NONE"
        in result.stdout
    )

    assert (
        _current_release_id(
            install_root
        )
        == RELEASE_A
    )


def test_rejects_relative_install_root() -> None:
    _require_switcher()

    result = _powershell(
        "-InstallRoot",
        "relative-root",
        "-TargetReleaseId",
        RELEASE_B,
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


def test_rejects_invalid_target_release_id(
    tmp_path: Path,
) -> None:
    _require_switcher()

    install_root = (
        tmp_path
        / "todoba"
    )

    result = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        "../outside",
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "TargetReleaseId must be one full lowercase Git SHA."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_missing_target_release(
    tmp_path: Path,
) -> None:
    _require_switcher()

    (
        install_root,
        release_a,
        _,
    ) = _make_install_root(
        tmp_path
    )

    current = (
        install_root
        / "current"
    )

    _make_junction(
        current,
        release_a,
    )

    missing_id = "c" * 40

    result = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        missing_id,
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "Target installed release does not exist."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_missing_current_pointer(
    tmp_path: Path,
) -> None:
    _require_switcher()

    (
        install_root,
        _,
        _,
    ) = _make_install_root(
        tmp_path
    )

    result = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        RELEASE_B,
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "Current release path does not exist."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_current_that_is_not_reparse_point(
    tmp_path: Path,
) -> None:
    _require_switcher()

    (
        install_root,
        _,
        _,
    ) = _make_install_root(
        tmp_path
    )

    current = (
        install_root
        / "current"
    )

    current.mkdir()

    (
        current
        / "VERSION"
    ).write_text(
        RELEASE_A + "\n",
        encoding="utf-8",
    )

    result = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        RELEASE_B,
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "Current release path is not a reparse-point junction."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_current_junction_outside_releases_root(
    tmp_path: Path,
) -> None:
    _require_switcher()

    (
        install_root,
        _,
        _,
    ) = _make_install_root(
        tmp_path
    )

    outside = (
        tmp_path
        / "outside-release"
    )

    outside.mkdir()

    (
        outside
        / "VERSION"
    ).write_text(
        RELEASE_A + "\n",
        encoding="utf-8",
    )

    current = (
        install_root
        / "current"
    )

    _make_junction(
        current,
        outside,
    )

    result = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        RELEASE_B,
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "Current junction target is outside installed release authority."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_tampered_target_fails_closed_and_preserves_current(
    tmp_path: Path,
) -> None:
    _require_switcher()

    (
        install_root,
        release_a,
        release_b,
    ) = _make_install_root(
        tmp_path
    )

    current = (
        install_root
        / "current"
    )

    _make_junction(
        current,
        release_a,
    )

    (
        release_b
        / "payload.txt"
    ).write_text(
        "tampered\n",
        encoding="utf-8",
    )

    result = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        RELEASE_B,
    )

    assert result.returncode != 0

    assert (
        "Release payload"
        in (
            result.stdout
            + result.stderr
        )
    )

    assert (
        _current_release_id(
            install_root
        )
        == RELEASE_A
    )


def test_switch_changes_current_to_verified_target(
    tmp_path: Path,
) -> None:
    _require_switcher()

    (
        install_root,
        release_a,
        _,
    ) = _make_install_root(
        tmp_path
    )

    current = (
        install_root
        / "current"
    )

    _make_junction(
        current,
        release_a,
    )

    result = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        RELEASE_B,
    )

    assert result.returncode == 0, (
        result.stdout
        + "\n"
        + result.stderr
    )

    assert (
        "TODOBA_RUNTIME_RELEASE_SWITCHED=TRUE"
        in result.stdout
    )

    assert (
        "PREVIOUS_RELEASE_ID="
        + RELEASE_A
        in result.stdout
    )

    assert (
        "CURRENT_RELEASE_ID="
        + RELEASE_B
        in result.stdout
    )

    assert (
        _current_release_id(
            install_root
        )
        == RELEASE_B
    )

    attributes = os.stat(
        current,
        follow_symlinks=False,
    ).st_file_attributes

    assert (
        attributes
        & 0x400
    ), "current must remain a Windows reparse-point junction"


def test_explicit_previous_release_supports_rollback(
    tmp_path: Path,
) -> None:
    _require_switcher()

    (
        install_root,
        release_a,
        _,
    ) = _make_install_root(
        tmp_path
    )

    current = (
        install_root
        / "current"
    )

    _make_junction(
        current,
        release_a,
    )

    forward = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        RELEASE_B,
    )

    assert forward.returncode == 0, (
        forward.stdout
        + "\n"
        + forward.stderr
    )

    rollback = _powershell(
        "-InstallRoot",
        str(install_root),
        "-TargetReleaseId",
        RELEASE_A,
    )

    assert rollback.returncode == 0, (
        rollback.stdout
        + "\n"
        + rollback.stderr
    )

    assert (
        "PREVIOUS_RELEASE_ID="
        + RELEASE_B
        in rollback.stdout
    )

    assert (
        "CURRENT_RELEASE_ID="
        + RELEASE_A
        in rollback.stdout
    )

    assert (
        _current_release_id(
            install_root
        )
        == RELEASE_A
    )


def test_switcher_owns_only_current_pointer_transition() -> None:
    _require_switcher()

    text = SWITCHER.read_text(
        encoding="utf-8-sig"
    )

    required = (
        "VERSION",
        "release-manifest.json",
        "SHA256SUMS",
        "Get-FileHash",
        "ItemType Junction",
        "TargetReleaseId",
    )

    for fragment in required:
        assert fragment in text

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
        "pip install",
        "-m venv",
        "Copy-Item",
    )

    for fragment in forbidden:
        assert fragment not in text
