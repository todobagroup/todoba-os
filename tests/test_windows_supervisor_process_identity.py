"""Behavioral identity tests for the Windows startup supervisor."""

import base64
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "scripts" / "start_todoba.ps1"


def _function_source() -> str:
    source = SUPERVISOR.read_text(encoding="utf-8")
    return source.split(
        "function Get-TodobaComponentProcess {", 1
    )[1].split(
        "function Start-TodobaComponent {", 1
    )[0]


def test_component_detection_requires_python_executable_identity():
    body = _function_source()
    assert "$pythonPath" in body
    assert "ExecutablePath" in body


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
@pytest.mark.parametrize(
    ("executable", "module", "expected"),
    [
        (r"C:\OtherPython\python.exe", "backend.start_api", "REJECT"),
        (r"C:\TODOBA\python.exe", "backend.start_api", "ACCEPT"),
        (r"C:\TODOBA\python.exe", "backend.other", "REJECT"),
    ],
)
def test_component_process_identity_behavior(executable, module, expected):
    body = _function_source()
    function_text = (
        "function Get-TodobaComponentProcess {" + body
    )

    script = r"""
$ErrorActionPreference = 'Stop'
$pythonPath = 'C:\TODOBA\python.exe'
$mockExecutable = '__EXECUTABLE__'
$mockModule = '__MODULE__'

function Get-CimInstance {
    @([PSCustomObject]@{
        Name = 'python.exe'
        ExecutablePath = $mockExecutable
        CommandLine = ('python.exe -m ' + $mockModule)
        ProcessId = 1234
    })
}

function Get-Process {
    [PSCustomObject]@{ Id = 1234 }
}

__FUNCTION__

$result = Get-TodobaComponentProcess -Module 'backend.start_api'

if ($null -eq $result) {
    Write-Output 'REJECT'
}
else {
    Write-Output 'ACCEPT'
}
"""

    script = (
        script.replace("__EXECUTABLE__", executable)
        .replace("__MODULE__", module)
        .replace("__FUNCTION__", function_text)
    )

    encoded = base64.b64encode(
        script.encode("utf-16-le")
    ).decode("ascii")

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected
