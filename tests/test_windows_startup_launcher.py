"""
TODOBA Windows Startup Launcher Tests

Proof:

Windows startup
->
one portable TODOBA launcher
->
Cloud API + supervised Telegram Executor
->
automatic recovery without duplicate runtimes
"""

import subprocess
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]

LAUNCHER_PATH = (
    ROOT_DIR
    / "scripts"
    / "start_todoba.ps1"
)


def read_launcher() -> str:
    return LAUNCHER_PATH.read_text(
        encoding="utf-8",
    )


def test_launcher_is_portable() -> None:
    launcher = read_launcher()

    assert "$PSScriptRoot" in launcher
    assert "E:\\TODOBA OS\\todoba-os" not in launcher
    assert ".venv\\Scripts\\python.exe" in launcher


def test_launcher_owns_api_and_remote_executor() -> None:
    launcher = read_launcher()

    assert "backend.start_api" in launcher
    assert "backend.start_executor" in launcher

    assert (
        '$env:TODOBA_RUNTIME_MODE = "CLOUD"'
        in launcher
    )

    assert (
        '$env:TELEGRAM_EXECUTION_MODE = '
        '"REMOTE_VPS"'
        in launcher
    )

    assert "cloudflared" not in launcher.lower()


def test_launcher_forces_python_utf8() -> None:
    launcher = read_launcher()

    assert (
        '$env:PYTHONUTF8 = "1"'
        in launcher
    )

    assert (
        '$env:PYTHONIOENCODING = "utf-8"'
        in launcher
    )


def test_launcher_prevents_duplicates_and_recovers() -> None:
    launcher = read_launcher()

    assert "Global\\TODOBA-Cloud-Runtime" in launcher
    assert "Start-Process" in launcher
    assert "HasExited" in launcher
    assert "Start-Sleep" in launcher


def test_launcher_supports_validation_and_logs() -> None:
    launcher = read_launcher()

    assert "[switch]$ValidateOnly" in launcher
    assert "TODOBA_STARTUP_VALIDATION=PASS" in launcher
    assert "data\\runtime_logs" in launcher
    assert "RedirectStandardOutput" in launcher
    assert "RedirectStandardError" in launcher


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_validates_in_windows_powershell() -> None:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(LAUNCHER_PATH),
            "-ValidateOnly",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0
    assert (
        "TODOBA_STARTUP_VALIDATION=PASS"
        in result.stdout
    )