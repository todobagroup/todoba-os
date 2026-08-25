"""
TODOBA Windows Runtime Controller Tests

Proof:

controlled runtime operations
->
Scheduled Task ownership
->
exact TODOBA process cleanup
->
safe Start, Stop, Restart, and Status
"""

import subprocess
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]

CONTROLLER_PATH = (
    ROOT_DIR
    / "scripts"
    / "control_todoba.ps1"
)


def read_controller() -> str:
    return CONTROLLER_PATH.read_text(
        encoding="utf-8",
    )


def test_controller_supports_required_actions() -> None:
    controller = read_controller()

    assert '"Status"' in controller
    assert '"Start"' in controller
    assert '"Stop"' in controller
    assert '"Restart"' in controller


def test_controller_owns_runtime_operations() -> None:
    controller = read_controller()

    assert "Get-ScheduledTask" in controller
    assert "Start-ScheduledTask" in controller
    assert "Stop-ScheduledTask" in controller
    assert "Stop-Process" in controller


def test_controller_targets_only_todoba_runtime() -> None:
    controller = read_controller()

    assert "python.exe" in controller
    assert (
        "backend\\.start_(api|executor)"
        in controller
    )
    assert "start_todoba.ps1" in controller
    assert "powershell.exe" in controller
    assert (
        "Get-TodobaStartupSupervisorProcesses"
        in controller
    )

    assert "cloudflared.exe" not in controller.lower()
    assert "Get-Service" not in controller


def test_controller_requires_safe_runtime_state() -> None:
    controller = read_controller()

    assert "Assert-TodobaAdministrator" in controller
    assert "old TODOBA processes still exist" in controller
    assert "Get-NetTCPConnection" in controller
    assert "Port8000Listening" in controller
    assert "SupervisorProcessCount" in controller
    assert "TODOBA runtime did not stop cleanly." in controller


def test_controller_stops_supervisor_before_waiting_for_clean_state() -> None:
    controller = read_controller()

    stop_body = controller.split(
        "function Stop-TodobaRuntime {",
        1,
    )[1].split(
        "function Start-TodobaRuntime {",
        1,
    )[0]

    stop_task_index = stop_body.index(
        "Stop-ScheduledTask"
    )

    supervisor_index = stop_body.index(
        "Get-TodobaStartupSupervisorProcesses"
    )

    runtime_process_index = stop_body.index(
        "Get-TodobaRuntimeProcesses"
    )

    clean_wait_index = stop_body.index(
        "$runtimeStopped = $false"
    )

    assert (
        stop_task_index
        < supervisor_index
        < runtime_process_index
        < clean_wait_index
    )

    assert (
        '$task.State.ToString() -eq "Ready"'
        in stop_body
    )

    assert (
        "$remainingSupervisors.Count -eq 0"
        in stop_body
    )

    assert (
        "$remainingProcesses.Count -eq 0"
        in stop_body
    )

    assert "$null -eq $listener" in stop_body


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell parser requires Windows.",
)
def test_controller_parses_in_windows_powershell() -> None:
    escaped_path = str(
        CONTROLLER_PATH
    ).replace(
        "'",
        "''",
    )

    command = (
        "$tokens=$null;"
        "$errors=$null;"
        "[System.Management.Automation.Language.Parser]::"
        f"ParseFile('{escaped_path}',"
        "[ref]$tokens,[ref]$errors)|Out-Null;"
        "if($errors.Count -gt 0){"
        "$errors|ForEach-Object{"
        "Write-Error $_.Message"
        "};"
        "exit 1"
        "};"
        "Write-Output "
        "'TODOBA_CONTROLLER_PARSE=PASS'"
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            command,
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0
    assert (
        "TODOBA_CONTROLLER_PARSE=PASS"
        in result.stdout
    )