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

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_uses_absolute_external_telegram_session_base_path(
    tmp_path: Path,
) -> None:
    session_base = (
        tmp_path
        / "telegram"
        / "todoba"
    ).resolve()

    session_base.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    session_file = Path(
        str(session_base)
        + ".session"
    )

    session_file.write_bytes(b"test-session")

    environment = __import__("os").environ.copy()

    environment["TELEGRAM_SESSION"] = str(
        session_base
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
        "TELEGRAM_SESSION_FILE="
        + str(session_file)
        in result.stdout
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_uses_absolute_external_telegram_session_file_path(
    tmp_path: Path,
) -> None:
    session_file = (
        tmp_path
        / "telegram"
        / "todoba.session"
    ).resolve()

    session_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    session_file.write_bytes(b"test-session")

    environment = __import__("os").environ.copy()

    environment["TELEGRAM_SESSION"] = str(
        session_file
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
        "TELEGRAM_SESSION_FILE="
        + str(session_file)
        in result.stdout
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_rejects_relative_external_telegram_session() -> None:
    environment = __import__("os").environ.copy()

    environment["TELEGRAM_SESSION"] = (
        "relative"
        + __import__("os").sep
        + "todoba"
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
        "TELEGRAM_SESSION must be an absolute path."
        in combined
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_rejects_missing_external_telegram_session(
    tmp_path: Path,
) -> None:
    session_base = (
        tmp_path
        / "telegram"
        / "missing-todoba"
    ).resolve()

    environment = __import__("os").environ.copy()

    environment["TELEGRAM_SESSION"] = str(
        session_base
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
        "TODOBA startup prerequisites are missing: TelegramSession"
        in combined
    )

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_uses_absolute_external_release_root(
    tmp_path: Path,
) -> None:
    release_root = (
        tmp_path
        / "release-001"
    ).resolve()

    (
        release_root
        / ".venv"
        / "Scripts"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        release_root
        / "backend"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        release_root
        / ".venv"
        / "Scripts"
        / "python.exe"
    ).write_bytes(b"placeholder")

    for name in (
        "start_api.py",
        "start_executor.py",
        "start_package_builder.py",
    ):
        (
            release_root
            / "backend"
            / name
        ).write_text(
            "",
            encoding="utf-8",
        )

    (
        release_root
        / ".env"
    ).write_text(
        "",
        encoding="utf-8",
    )

    (
        release_root
        / "todoba.session"
    ).write_bytes(
        b"placeholder"
    )

    environment = __import__("os").environ.copy()

    environment["TODOBA_RELEASE_ROOT"] = str(
        release_root
    )

    environment.pop(
        "TODOBA_ENV_FILE",
        None,
    )

    environment.pop(
        "TELEGRAM_SESSION",
        None,
    )

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

    assert (
        "RELEASE_ROOT="
        + str(release_root)
        in result.stdout
    )

    assert (
        "PYTHON_PATH="
        + str(
            (
                release_root
                / ".venv"
                / "Scripts"
                / "python.exe"
            ).resolve()
        )
        in result.stdout
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_rejects_relative_external_release_root() -> None:
    environment = __import__("os").environ.copy()

    environment["TODOBA_RELEASE_ROOT"] = (
        "relative"
        + __import__("os").sep
        + "release"
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
        "TODOBA_RELEASE_ROOT must be an absolute path."
        in combined
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_preserves_default_release_root() -> None:
    environment = __import__("os").environ.copy()

    environment.pop(
        "TODOBA_RELEASE_ROOT",
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

    assert (
        "RELEASE_ROOT="
        + str(ROOT_DIR.resolve())
        in result.stdout
    )

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_uses_absolute_external_python_executable(
    tmp_path: Path,
) -> None:
    python_executable = (
        tmp_path
        / "runtime"
        / "python"
        / "python.exe"
    ).resolve()

    python_executable.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    python_executable.write_bytes(
        b"placeholder"
    )

    environment = __import__("os").environ.copy()

    environment["TODOBA_PYTHON_EXECUTABLE"] = str(
        python_executable
    )

    environment.pop(
        "TODOBA_RELEASE_ROOT",
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

    assert (
        "PYTHON_PATH="
        + str(python_executable)
        in result.stdout
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_rejects_relative_external_python_executable() -> None:
    environment = __import__("os").environ.copy()

    environment["TODOBA_PYTHON_EXECUTABLE"] = (
        "relative"
        + __import__("os").sep
        + "python.exe"
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
        "TODOBA_PYTHON_EXECUTABLE must be an absolute path."
        in combined
    )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_rejects_missing_external_python_executable(
    tmp_path: Path,
) -> None:
    missing_python = (
        tmp_path
        / "runtime"
        / "python"
        / "missing-python.exe"
    ).resolve()

    environment = __import__("os").environ.copy()

    environment["TODOBA_PYTHON_EXECUTABLE"] = str(
        missing_python
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
        "TODOBA startup prerequisites are missing: Python"
        in combined
    )

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows PowerShell validation requires Windows.",
)
def test_launcher_validate_only_survives_relocation_with_external_runtime_authorities(
    tmp_path: Path,
) -> None:
    import os
    import shutil

    runtime_root = (
        tmp_path
        / "stable-runtime"
    ).resolve()

    runtime_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    relocated_launcher = (
        runtime_root
        / "start_todoba.ps1"
    )

    shutil.copy2(
        LAUNCHER_PATH,
        relocated_launcher,
    )

    release_root = (
        tmp_path
        / "releases"
        / "release-001"
    ).resolve()

    backend_root = (
        release_root
        / "backend"
    )

    backend_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name in (
        "start_api.py",
        "start_executor.py",
        "start_package_builder.py",
    ):
        (
            backend_root
            / name
        ).write_text(
            "",
            encoding="utf-8",
        )

    python_executable = (
        tmp_path
        / "python-runtime"
        / "python.exe"
    ).resolve()

    python_executable.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    python_executable.write_bytes(
        b"placeholder"
    )

    environment_file = (
        tmp_path
        / "shared"
        / "config"
        / ".env"
    ).resolve()

    environment_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    environment_file.write_text(
        "",
        encoding="utf-8",
    )

    telegram_identifier = (
        tmp_path
        / "shared"
        / "telegram"
        / "todoba"
    ).resolve()

    telegram_identifier.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    telegram_file = Path(
        str(telegram_identifier)
        + ".session"
    )

    telegram_file.write_bytes(
        b"placeholder"
    )

    log_root = (
        tmp_path
        / "shared"
        / "logs"
    ).resolve()

    environment = os.environ.copy()

    environment["TODOBA_RELEASE_ROOT"] = str(
        release_root
    )

    environment["TODOBA_PYTHON_EXECUTABLE"] = str(
        python_executable
    )

    environment["TODOBA_ENV_FILE"] = str(
        environment_file
    )

    environment["TELEGRAM_SESSION"] = str(
        telegram_identifier
    )

    environment["TODOBA_RUNTIME_LOG_ROOT"] = str(
        log_root
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(relocated_launcher),
            "-ValidateOnly",
        ],
        cwd=runtime_root,
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
        "RELEASE_ROOT="
        + str(release_root)
        in result.stdout
    )

    assert (
        "PYTHON_PATH="
        + str(python_executable)
        in result.stdout
    )

    assert (
        "ENVIRONMENT_PATH="
        + str(environment_file)
        in result.stdout
    )

    assert (
        "TELEGRAM_SESSION_FILE="
        + str(telegram_file)
        in result.stdout
    )

    assert (
        "LOG_DIRECTORY="
        + str(log_root)
        in result.stdout
    )