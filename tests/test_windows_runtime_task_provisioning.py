from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]

PROVISIONER_PATH = (
    ROOT_DIR
    / "scripts"
    / "provision_todoba_runtime_task.ps1"
)


def _run_validate_only(
    launcher_path: Path | str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PROVISIONER_PATH),
            "-LauncherPath",
            str(launcher_path),
            "-ValidateOnly",
        ],
        cwd=ROOT_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_runtime_task_provisioner_exists() -> None:
    assert PROVISIONER_PATH.is_file()


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows Scheduled Task provisioning is Windows-only.",
)
def test_validate_only_locks_stable_runtime_task_binding(
    tmp_path: Path,
) -> None:
    runtime_root = (
        tmp_path
        / "runtime"
    ).resolve()

    runtime_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    launcher = (
        runtime_root
        / "start_todoba.ps1"
    )

    launcher.write_text(
        "# placeholder\n",
        encoding="utf-8",
    )

    result = _run_validate_only(
        launcher
    )

    assert result.returncode == 0, (
        result.stdout
        + result.stderr
    )

    expected = {
        "TODOBA_RUNTIME_TASK_VALIDATION=PASS",
        "TASK_NAME=TODOBA Runtime",
        "TASK_EXECUTE=powershell.exe",
        "TASK_LAUNCHER_PATH="
        + str(launcher),
        "TASK_WORKING_DIRECTORY="
        + str(runtime_root),
        "TASK_USER=SYSTEM",
        "TASK_LOGON_TYPE=ServiceAccount",
        "TASK_RUN_LEVEL=Highest",
        "TASK_TRIGGER=AtStartup",
        "TASK_MUTATION=NONE",
    }

    for line in expected:
        assert line in result.stdout

    arguments_line = next(
        line
        for line in result.stdout.splitlines()
        if line.startswith(
            "TASK_ARGUMENTS="
        )
    )

    assert "-NoProfile" in arguments_line
    assert "-WindowStyle Hidden" in arguments_line
    assert "-ExecutionPolicy Bypass" in arguments_line
    assert "-File" in arguments_line
    assert f'"{launcher}"' in arguments_line


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows Scheduled Task provisioning is Windows-only.",
)
def test_validate_only_rejects_relative_launcher_path() -> None:
    result = _run_validate_only(
        Path("relative")
        / "start_todoba.ps1"
    )

    assert result.returncode != 0

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "LauncherPath must be an absolute path."
        in combined
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows Scheduled Task provisioning is Windows-only.",
)
def test_validate_only_rejects_missing_launcher(
    tmp_path: Path,
) -> None:
    missing = (
        tmp_path
        / "runtime"
        / "start_todoba.ps1"
    ).resolve()

    result = _run_validate_only(
        missing
    )

    assert result.returncode != 0

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "LauncherPath does not exist."
        in combined
    )


def test_provisioner_contract_declares_single_task_owner() -> None:
    source = PROVISIONER_PATH.read_text(
        encoding="utf-8"
    )

    required = (
        '$taskName = "TODOBA Runtime"',
        "Register-ScheduledTask",
        "New-ScheduledTaskAction",
        "New-ScheduledTaskPrincipal",
        "New-ScheduledTaskTrigger",
        "AtStartup",
        '"SYSTEM"',
        '"ServiceAccount"',
        '"Highest"',
        "[switch]$ValidateOnly",
    )

    for fragment in required:
        assert fragment in source


def test_controller_remains_non_provisioning_owner() -> None:
    controller = (
        ROOT_DIR
        / "scripts"
        / "control_todoba.ps1"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "Register-ScheduledTask",
        "New-ScheduledTaskAction",
        "New-ScheduledTaskPrincipal",
        "New-ScheduledTaskTrigger",
    )

    for fragment in forbidden:
        assert fragment not in controller
