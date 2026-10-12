from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PROVISIONER = (
    ROOT
    / "scripts"
    / "provision_todoba_runtime_environment.ps1"
)


def _require_provisioner() -> None:
    assert PROVISIONER.is_file(), (
        "Persistent production runtime environment "
        "provisioner does not exist."
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
            str(PROVISIONER),
            *arguments,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_runtime_environment_provisioner_exists() -> None:
    _require_provisioner()


def test_validate_only_accepts_locked_production_authorities() -> None:
    _require_provisioner()

    result = _powershell(
        "-ReleaseRoot",
        r"C:\TODOBA\current",
        "-PythonExecutable",
        r"C:\TODOBA\python\Scripts\python.exe",
        "-EnvironmentFile",
        r"C:\TODOBA\shared\config\.env",
        "-TelegramSession",
        r"C:\TODOBA\shared\telegram\todoba.session",
        "-RuntimeLogRoot",
        r"C:\TODOBA\shared\logs",
        "-ValidateOnly",
    )

    assert result.returncode == 0, (
        result.stdout
        + "\n"
        + result.stderr
    )

    output = result.stdout

    assert (
        "TODOBA_RUNTIME_ENVIRONMENT_VALIDATION=PASS"
        in output
    )

    assert (
        r"TODOBA_RELEASE_ROOT=C:\TODOBA\current"
        in output
    )

    assert (
        r"TODOBA_PYTHON_EXECUTABLE="
        r"C:\TODOBA\python\Scripts\python.exe"
        in output
    )

    assert (
        r"TODOBA_ENV_FILE="
        r"C:\TODOBA\shared\config\.env"
        in output
    )

    assert (
        r"TELEGRAM_SESSION="
        r"C:\TODOBA\shared\telegram\todoba.session"
        in output
    )

    assert (
        r"TODOBA_RUNTIME_LOG_ROOT="
        r"C:\TODOBA\shared\logs"
        in output
    )

    assert "PERSISTENCE_SCOPE=Machine" in output
    assert "ENVIRONMENT_MUTATION=NONE" in output


def test_rejects_relative_release_root() -> None:
    _require_provisioner()

    result = _powershell(
        "-ReleaseRoot",
        r"current",
        "-PythonExecutable",
        r"C:\TODOBA\python\Scripts\python.exe",
        "-EnvironmentFile",
        r"C:\TODOBA\shared\config\.env",
        "-TelegramSession",
        r"C:\TODOBA\shared\telegram\todoba.session",
        "-RuntimeLogRoot",
        r"C:\TODOBA\shared\logs",
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "ReleaseRoot must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_relative_python_executable() -> None:
    _require_provisioner()

    result = _powershell(
        "-ReleaseRoot",
        r"C:\TODOBA\current",
        "-PythonExecutable",
        r"python\Scripts\python.exe",
        "-EnvironmentFile",
        r"C:\TODOBA\shared\config\.env",
        "-TelegramSession",
        r"C:\TODOBA\shared\telegram\todoba.session",
        "-RuntimeLogRoot",
        r"C:\TODOBA\shared\logs",
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "PythonExecutable must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_relative_environment_file() -> None:
    _require_provisioner()

    result = _powershell(
        "-ReleaseRoot",
        r"C:\TODOBA\current",
        "-PythonExecutable",
        r"C:\TODOBA\python\Scripts\python.exe",
        "-EnvironmentFile",
        r"shared\config\.env",
        "-TelegramSession",
        r"C:\TODOBA\shared\telegram\todoba.session",
        "-RuntimeLogRoot",
        r"C:\TODOBA\shared\logs",
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "EnvironmentFile must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_relative_telegram_session() -> None:
    _require_provisioner()

    result = _powershell(
        "-ReleaseRoot",
        r"C:\TODOBA\current",
        "-PythonExecutable",
        r"C:\TODOBA\python\Scripts\python.exe",
        "-EnvironmentFile",
        r"C:\TODOBA\shared\config\.env",
        "-TelegramSession",
        r"shared\telegram\todoba.session",
        "-RuntimeLogRoot",
        r"C:\TODOBA\shared\logs",
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "TelegramSession must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_relative_runtime_log_root() -> None:
    _require_provisioner()

    result = _powershell(
        "-ReleaseRoot",
        r"C:\TODOBA\current",
        "-PythonExecutable",
        r"C:\TODOBA\python\Scripts\python.exe",
        "-EnvironmentFile",
        r"C:\TODOBA\shared\config\.env",
        "-TelegramSession",
        r"C:\TODOBA\shared\telegram\todoba.session",
        "-RuntimeLogRoot",
        r"shared\logs",
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "RuntimeLogRoot must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_provisioner_owns_exact_five_machine_authorities() -> None:
    _require_provisioner()

    text = PROVISIONER.read_text(
        encoding="utf-8-sig"
    )

    required = (
        "TODOBA_RELEASE_ROOT",
        "TODOBA_PYTHON_EXECUTABLE",
        "TODOBA_ENV_FILE",
        "TELEGRAM_SESSION",
        "TODOBA_RUNTIME_LOG_ROOT",
        "EnvironmentVariableTarget]::Machine",
        "SetEnvironmentVariable",
    )

    for fragment in required:
        assert fragment in text


def test_provisioner_does_not_own_task_process_or_release_switch() -> None:
    _require_provisioner()

    text = PROVISIONER.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "Register-ScheduledTask",
        "Set-ScheduledTask",
        "Start-ScheduledTask",
        "Stop-ScheduledTask",
        "Start-Process",
        "Stop-Process",
        "ItemType Junction",
        "New-Item -ItemType Junction",
        "Move-Item",
        "install_todoba_runtime_release",
        "provision_todoba_python_runtime",
    )

    for fragment in forbidden:
        assert fragment not in text


def test_provisioner_never_embeds_secret_values() -> None:
    _require_provisioner()

    text = PROVISIONER.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "TODOBA_PAYPAL_CLIENT_SECRET",
        "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY",
        "TELEGRAM_API_HASH",
        "TELEGRAM_API_ID",
    )

    for fragment in forbidden:
        assert fragment not in text
