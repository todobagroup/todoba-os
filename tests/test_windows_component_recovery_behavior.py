"""Isolated behavioral probes of the TODOBA PowerShell supervisor loop.

Never invokes the production launcher, actual module entrypoints, Scheduled
Tasks, or real component processes. All component and timing APIs are mocked.
"""

import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "start_todoba.ps1"


def _probe(*, fail_restart: bool) -> subprocess.CompletedProcess[str]:
    # Encode the entire command to avoid cmdline quoting/PSReadLine issues.
    fail_literal = "$true" if fail_restart else "$false"
    script = r'''
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
try {
    $sourcePath = '__LAUNCHER_PATH__'
    $tokens = $null
    $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile(
        $sourcePath, [ref]$tokens, [ref]$parseErrors
    )
    if (@($parseErrors | Where-Object { $null -ne $_ }).Count -ne 0) {
        throw 'LAUNCHER_PARSE_FAILED'
    }
    $loops = @($ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.WhileStatementAst]
    }, $true))
    if ($loops.Count -ne 1) {
        throw 'SUPERVISOR_LOOP_BOUNDARY_CHANGED'
    }
    $loopText = $loops[0].Extent.Text
    $RestartDelaySeconds = 1
    $script:starts = 0
    $script:cycles = 0
    $script:failRestart = __FAIL_RESTART__

    function Write-TodobaRuntimeLog { param([string]$Message) }
    function Start-TodobaComponent {
        param([string]$Name, [string]$Module)
        $script:starts++
        if ($script:failRestart) { throw 'SIMULATED_RESTART_FAILURE' }
        $p = [pscustomobject]@{ HasExited = $false }
        $p | Add-Member -MemberType ScriptMethod -Name Refresh -Value { }
        return $p
    }
    function Start-Sleep {
        param([int]$Seconds)
        if ($Seconds -eq 2) {
            $script:cycles++
            if ($script:cycles -ge 2) { throw 'SANDBOX_LOOP_COMPLETE' }
        }
    }
    $dead = [pscustomobject]@{ HasExited = $true }
    $dead | Add-Member -MemberType ScriptMethod -Name Refresh -Value { }
    $components = @([pscustomobject]@{
        Name = 'api'
        Module = 'backend.start_api'
        Process = $dead
        Owned = $true
    })

    $observed = ''
    try {
        Invoke-Expression $loopText
        throw 'SUPERVISOR_LOOP_RETURNED_UNEXPECTEDLY'
    }
    catch { $observed = $_.Exception.Message }

    if ($script:starts -ne 1) { throw "BAD_RESTART_COUNT=$script:starts" }
    if ($script:failRestart) {
        if ($observed -cne 'SIMULATED_RESTART_FAILURE') {
            throw "FAILURE_NOT_PROPAGATED=$observed"
        }
        Write-Output 'FAILURE_PROPAGATION=PASS'
    }
    else {
        if ($observed -cne 'SANDBOX_LOOP_COMPLETE') {
            throw "LOOP_UNEXPECTED_RESULT=$observed"
        }
        if ($components[0].Process.HasExited) {
            throw 'COMPONENT_NOT_REPLACED'
        }
        Write-Output 'COMPONENT_RESTART=PASS'
    }
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
'''
    # Escape embedded path for PowerShell single-quoted string.
    script = script.replace("__LAUNCHER_PATH__", str(LAUNCHER).replace("'", "''"))
    script = script.replace("__FAIL_RESTART__", fail_literal)
    encoded = __import__("base64").b64encode(script.encode("utf-16-le")).decode("ascii")
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _assert_no_powershell_errors(stderr: str) -> None:
    """Allow only PowerShell CLIXML progress records, never error/warning text."""
    if not stderr.strip():
        return
    prefix = "#< CLIXML\n"
    assert stderr.startswith(prefix), f"Unexpected PowerShell stderr: {stderr!r}"
    try:
        root = ElementTree.fromstring(stderr[len(prefix):])
    except ElementTree.ParseError as exc:
        pytest.fail(f"Malformed PowerShell stderr CLIXML: {exc}")
    namespace = "http://schemas.microsoft.com/powershell/2004/04"
    assert root.tag == f"{{{namespace}}}Objs", "Unknown PowerShell stderr XML"
    records = list(root)
    assert records, "Empty CLIXML stderr"
    assert all(
        obj.tag == f"{{{namespace}}}Obj" and obj.get("S") == "progress"
        for obj in records
    ), "PowerShell emitted a non-progress stderr record"


@pytest.mark.parametrize("stderr", [
    "Unexpected error",
    '#< CLIXML\n<Objs xmlns="http://schemas.microsoft.com/powershell/2004/04"><Obj S="error"/></Objs>',
])
def test_stderr_guard_rejects_errors(stderr: str) -> None:
    with pytest.raises(AssertionError):
        _assert_no_powershell_errors(stderr)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell only")
def test_dead_component_restart_from_actual_loop() -> None:
    result = _probe(fail_restart=False)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stdout.strip() == "COMPONENT_RESTART=PASS"
    _assert_no_powershell_errors(result.stderr)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell only")
def test_restart_failure_propagates_from_actual_loop() -> None:
    result = _probe(fail_restart=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stdout.strip() == "FAILURE_PROPAGATION=PASS"
    _assert_no_powershell_errors(result.stderr)
