param(
    [switch]$ValidateOnly,

    [ValidateRange(1, 300)]
    [int]$RestartDelaySeconds = 5
)

# TODOBA Windows Startup Launcher
#
# Owns:
# - Cloud API process
# - supervised Telegram Executor process
# - duplicate runtime prevention
# - child process recovery
# - runtime logs
#
# It never executes broker orders.

Set-StrictMode -Version Latest

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path `
-Parent `
$PSScriptRoot

$pythonPath = Join-Path `
$repoRoot `
".venv\Scripts\python.exe"

$environmentPath = Join-Path `
$repoRoot `
".env"

$telegramSessionPath = Join-Path `
$repoRoot `
"todoba.session"

$apiEntryPath = Join-Path `
$repoRoot `
"backend\start_api.py"

$executorEntryPath = Join-Path `
$repoRoot `
"backend\start_executor.py"

$logDirectory = Join-Path `
$repoRoot `
"data\runtime_logs"

$env:TODOBA_RUNTIME_MODE = "CLOUD"
$env:TELEGRAM_EXECUTION_MODE = "REMOTE_VPS"


$requiredPaths = [ordered]@{
    Python = $pythonPath
    Environment = $environmentPath
    TelegramSession = $telegramSessionPath
    ApiEntry = $apiEntryPath
    ExecutorEntry = $executorEntryPath
}


$missingPaths = @()

foreach (
    $requiredPath
    in $requiredPaths.GetEnumerator()
) {
    if (
        -not (
            Test-Path `
            -LiteralPath $requiredPath.Value
        )
    ) {
        $missingPaths += $requiredPath.Name
    }
}


if ($missingPaths.Count -gt 0) {
    $missingText = (
        $missingPaths -join ", "
    )

    throw (
        "TODOBA startup prerequisites are missing: $missingText"
    )
}


if ($ValidateOnly) {
    Write-Output "TODOBA_STARTUP_VALIDATION=PASS"
    Write-Output "REPO_ROOT=$repoRoot"
    Write-Output "PYTHON_PATH=$pythonPath"
    Write-Output "API_MODULE=backend.start_api"
    Write-Output "EXECUTOR_MODULE=backend.start_executor"

    exit 0
}


New-Item `
-ItemType Directory `
-Path $logDirectory `
-Force |
Out-Null


$supervisorLogPath = Join-Path `
$logDirectory `
"startup-supervisor.log"


function Write-TodobaRuntimeLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $timestamp = Get-Date `
    -Format "yyyy-MM-ddTHH:mm:ss"

    $line = "$timestamp $Message"

    Add-Content `
    -LiteralPath $supervisorLogPath `
    -Value $line `
    -Encoding UTF8

    Write-Host $line
}


function Get-TodobaComponentProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Module
    )

    $candidates = @(
        Get-CimInstance `
        Win32_Process `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $isPython = (
                $_.Name -eq "python.exe"
            ) -or (
                $_.Name -eq "pythonw.exe"
            )

            $hasModule = $false

            if ($null -ne $_.CommandLine) {
                $hasModule = (
                    $_.CommandLine.Contains(
                        "-m $Module"
                    )
                )
            }

            $isPython -and $hasModule
        }
    )

    foreach ($candidate in $candidates) {
        $process = Get-Process `
        -Id $candidate.ProcessId `
        -ErrorAction SilentlyContinue

        if ($null -ne $process) {
            return $process
        }
    }

    return $null
}


function Start-TodobaComponent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Module
    )

    $timestamp = Get-Date `
    -Format "yyyyMMdd-HHmmss"

    $standardOutputPath = Join-Path `
    $logDirectory `
    "$Name.$timestamp.out.log"

    $standardErrorPath = Join-Path `
    $logDirectory `
    "$Name.$timestamp.err.log"

    Write-TodobaRuntimeLog (
        "Starting $Name module=$Module"
    )

    $startParameters = @{
        FilePath = $pythonPath
        ArgumentList = @(
            "-u",
            "-m",
            $Module
        )
        WorkingDirectory = $repoRoot
        WindowStyle = "Hidden"
        RedirectStandardOutput = (
            $standardOutputPath
        )
        RedirectStandardError = (
            $standardErrorPath
        )
        PassThru = $true
    }

    $startedProcess = Start-Process `
    @startParameters

    return $startedProcess
}


$mutexName = "Global\TODOBA-Cloud-Runtime"

$createdNew = $false

$runtimeMutex = (
    [System.Threading.Mutex]::new(
        $true,
        $mutexName,
        [ref]$createdNew
    )
)


if (-not $createdNew) {
    Write-Output (
        "TODOBA runtime is already running."
    )

    $runtimeMutex.Dispose()

    exit 0
}


$components = @(
    [PSCustomObject]@{
        Name = "api"
        Module = "backend.start_api"
        Process = $null
        Owned = $false
    },
    [PSCustomObject]@{
        Name = "executor"
        Module = "backend.start_executor"
        Process = $null
        Owned = $false
    }
)


try {
    Write-TodobaRuntimeLog (
        "TODOBA startup supervisor running."
    )

    foreach ($component in $components) {
        $existingProcess = (
            Get-TodobaComponentProcess `
            -Module $component.Module
        )

        if ($null -ne $existingProcess) {
            $component.Process = $existingProcess
            $component.Owned = $false

           Write-TodobaRuntimeLog (
    "Adopted existing $($component.Name) process pid=$($existingProcess.Id)"
 )
        }
        else {
            $component.Process = (
                Start-TodobaComponent `
                -Name $component.Name `
                -Module $component.Module
            )

            $component.Owned = $true
        }
    }

    while ($true) {
        foreach ($component in $components) {
            $shouldRestart = (
                $null -eq $component.Process
            )

            if (-not $shouldRestart) {
                try {
                    $component.Process.Refresh()

                    $shouldRestart = (
                        $component.Process.HasExited
                    )
                }
                catch {
                    $shouldRestart = $true
                }
            }

            if ($shouldRestart) {
                Write-TodobaRuntimeLog (
                    "$($component.Name) stopped. Restarting after $RestartDelaySeconds seconds."
  )
                Start-Sleep `
                -Seconds $RestartDelaySeconds

                $component.Process = (
                    Start-TodobaComponent `
                    -Name $component.Name `
                    -Module $component.Module
                )

                $component.Owned = $true
            }
        }

        Start-Sleep -Seconds 2
    }
}
finally {
    foreach ($component in $components) {
        $shouldStop = $false

        if (
            $component.Owned -and
            $null -ne $component.Process
   ) {
            try {
                $component.Process.Refresh()

                $shouldStop = (
                    -not $component.Process.HasExited
                )
            }
            catch {
                $shouldStop = $false
            }
        }

        if ($shouldStop) {
            Stop-Process `
            -Id $component.Process.Id `
            -Force `
            -ErrorAction SilentlyContinue
        }
    }

    if ($createdNew) {
        $runtimeMutex.ReleaseMutex()
    }

    $runtimeMutex.Dispose()

    Write-TodobaRuntimeLog (
        "TODOBA startup supervisor stopped."
    )
}