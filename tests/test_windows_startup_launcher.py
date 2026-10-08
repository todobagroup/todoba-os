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

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_uses_absolute_external_runtime_config(
    tmp_path: Path,
) -> None:
    external_env = (
        tmp_path
        / "production.env"
    )

    external_env.write_text(
        "TODOBA_API_HOST=127.0.0.1\n",
        encoding="utf-8",
    )

    environment = __import__("os").environ.copy()

    environment["TODOBA_ENV_FILE"] = str(
        external_env.resolve()
    )

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
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, (
        result.stdout
        + result.stderr
    )

    assert (
        "ENVIRONMENT_PATH="
        + str(
            external_env.resolve()
        )
        in result.stdout
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_rejects_relative_external_runtime_config() -> None:
    environment = __import__("os").environ.copy()

    environment["TODOBA_ENV_FILE"] = (
        "relative"
        + __import__("os").sep
        + "production.env"
    )

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
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode != 0

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "TODOBA_ENV_FILE must be an absolute path."
        in combined
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_rejects_missing_external_runtime_config(
    tmp_path: Path,
) -> None:
    missing_env = (
        tmp_path
        / "missing-production.env"
    ).resolve()

    environment = __import__("os").environ.copy()

    environment["TODOBA_ENV_FILE"] = str(
        missing_env
    )

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
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode != 0

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "TODOBA startup prerequisites are missing: Environment"
        in combined
    )

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_uses_absolute_external_runtime_log_root(
    tmp_path: Path,
) -> None:
    external_log_root = (
        tmp_path
        / "shared-runtime-logs"
    ).resolve()

    assert not external_log_root.exists()

    environment = __import__("os").environ.copy()

    environment["TODOBA_RUNTIME_LOG_ROOT"] = str(
        external_log_root
    )

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
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, (
        result.stdout
        + result.stderr
    )

    assert (
        "LOG_DIRECTORY="
        + str(external_log_root)
        in result.stdout
    )

    assert not external_log_root.exists()


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_rejects_relative_external_runtime_log_root() -> None:
    environment = __import__("os").environ.copy()

    environment["TODOBA_RUNTIME_LOG_ROOT"] = (
        "relative"
        + __import__("os").sep
        + "runtime-logs"
    )

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
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode != 0

    combined = (
        result.stdout
        + result.stderr
    )

    assert (
        "TODOBA_RUNTIME_LOG_ROOT must be an absolute path."
        in combined
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_preserves_default_runtime_log_root() -> None:
    environment = __import__("os").environ.copy()

    environment.pop(
        "TODOBA_RUNTIME_LOG_ROOT",
        None,
    )

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
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, (
        result.stdout
        + result.stderr
    )

    expected_log_root = (
        ROOT_DIR
        / "data"
        / "runtime_logs"
    ).resolve()

    assert (
        "LOG_DIRECTORY="
        + str(expected_log_root)
        in result.stdout
    )