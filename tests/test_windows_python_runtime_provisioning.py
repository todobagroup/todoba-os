from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PROVISIONER = (
    ROOT
    / "scripts"
    / "provision_todoba_python_runtime.ps1"
)

REQUIREMENTS = (
    ROOT
    / "requirements-production.txt"
)

DEV_BASE_PYTHON = Path(
    r"C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe"
)


def _require_provisioner() -> None:
    assert PROVISIONER.is_file(), (
        "Production Python runtime provisioner "
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
            str(PROVISIONER),
            *arguments,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_python_runtime_provisioner_exists() -> None:
    _require_provisioner()


def test_validate_only_accepts_explicit_absolute_authorities(
    tmp_path: Path,
) -> None:
    _require_provisioner()

    runtime_root = (
        tmp_path
        / "python-runtime"
    )

    result = _powershell(
        "-BasePythonPath",
        str(DEV_BASE_PYTHON),
        "-RuntimeRoot",
        str(runtime_root),
        "-RequirementsPath",
        str(REQUIREMENTS),
        "-ValidateOnly",
    )

    assert result.returncode == 0, (
        result.stdout
        + "\n"
        + result.stderr
    )

    assert (
        "TODOBA_PYTHON_RUNTIME_VALIDATION=PASS"
        in result.stdout
    )

    assert "PYTHON_MAJOR_MINOR=3.13" in result.stdout
    assert "PYTHON_BITS=64" in result.stdout
    assert "RUNTIME_MUTATION=NONE" in result.stdout

    assert not runtime_root.exists()


def test_rejects_relative_base_python(
    tmp_path: Path,
) -> None:
    _require_provisioner()

    result = _powershell(
        "-BasePythonPath",
        r"Python313\python.exe",
        "-RuntimeRoot",
        str(tmp_path / "runtime"),
        "-RequirementsPath",
        str(REQUIREMENTS),
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "BasePythonPath must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_relative_runtime_root() -> None:
    _require_provisioner()

    result = _powershell(
        "-BasePythonPath",
        str(DEV_BASE_PYTHON),
        "-RuntimeRoot",
        "relative-runtime",
        "-RequirementsPath",
        str(REQUIREMENTS),
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


def test_rejects_relative_requirements_path(
    tmp_path: Path,
) -> None:
    _require_provisioner()

    result = _powershell(
        "-BasePythonPath",
        str(DEV_BASE_PYTHON),
        "-RuntimeRoot",
        str(tmp_path / "runtime"),
        "-RequirementsPath",
        "requirements-production.txt",
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "RequirementsPath must be an absolute path."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_missing_base_python(
    tmp_path: Path,
) -> None:
    _require_provisioner()

    missing_python = (
        tmp_path
        / "missing"
        / "python.exe"
    )

    result = _powershell(
        "-BasePythonPath",
        str(missing_python),
        "-RuntimeRoot",
        str(tmp_path / "runtime"),
        "-RequirementsPath",
        str(REQUIREMENTS),
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "BasePythonPath does not exist."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_rejects_existing_runtime_root(
    tmp_path: Path,
) -> None:
    _require_provisioner()

    runtime_root = (
        tmp_path
        / "runtime"
    )

    runtime_root.mkdir()

    result = _powershell(
        "-BasePythonPath",
        str(DEV_BASE_PYTHON),
        "-RuntimeRoot",
        str(runtime_root),
        "-RequirementsPath",
        str(REQUIREMENTS),
        "-ValidateOnly",
    )

    assert result.returncode != 0

    assert (
        "RuntimeRoot already exists."
        in (
            result.stdout
            + result.stderr
        )
    )


def test_requirements_are_exact_pinned_production_authority() -> None:
    _require_provisioner()

    lines = [
        line.strip()
        for line in REQUIREMENTS.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    assert lines == [
        "fastapi==0.141.1",
        "uvicorn==0.53.0",
        "pydantic==2.13.5",
        "python-dotenv==1.2.3",
        "telethon==1.45.0",
        "MetaTrader5==5.0.6180",
        "httpx==0.28.1",
        "cryptography==50.0.1",
    ]


def test_provisioner_does_not_own_other_production_authorities() -> None:
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
        "SetEnvironmentVariable",
        "TODOBA_RELEASE_ROOT",
        "TODOBA_ENV_FILE",
        "TELEGRAM_SESSION",
        "TODOBA_RUNTIME_LOG_ROOT",
        "ItemType Junction",
    )

    for fragment in forbidden:
        assert fragment not in text
