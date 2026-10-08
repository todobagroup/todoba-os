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
# - supervised customer package builder process
# - duplicate runtime prevention
# - child process recovery
# - runtime logs
#
# It never executes broker orders.

Set-StrictMode -Version Latest

$ErrorActionPreference = "Stop"

function Test-TodobaAbsoluteWindowsPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (
        $Path -match '^[A-Za-z]:[\\/]'
    ) {
        return $true
    }

    if (
        $Path -match '^\\\\[^\\/]+[\\/][^\\/]+'
    ) {
        return $true
    }

    return $false
}

$defaultReleaseRoot = Split-Path `
    -Parent `
    $PSScriptRoot

$releaseRootOverride = (
    [Environment]::GetEnvironmentVariable(
        "TODOBA_RELEASE_ROOT"
    )
)

if (
    [string]::IsNullOrWhiteSpace(
        $releaseRootOverride
    )
) {
    $releaseRoot = (
        [System.IO.Path]::GetFullPath(
            $defaultReleaseRoot
        )
    )
}
else {
    $releaseRootOverride = (
        $releaseRootOverride.Trim()
    )

    if (
        -not (
            Test-TodobaAbsoluteWindowsPath `
                -Path $releaseRootOverride
        )
    ) {
        throw (
            "TODOBA_RELEASE_ROOT must be an absolute path."
        )
    }

    $releaseRoot = (
        [System.IO.Path]::GetFullPath(
            $releaseRootOverride
        )
    )

    $env:TODOBA_RELEASE_ROOT = $releaseRoot
}

$repoRoot = $releaseRoot

$pythonPath = Join-Path `
$repoRoot `
".venv\Scripts\python.exe"

$environmentOverride = (
    [Environment]::GetEnvironmentVariable(
        "TODOBA_ENV_FILE"
    )
)

if (
    [string]::IsNullOrWhiteSpace(
        $environmentOverride
    )
) {
    $environmentPath = Join-Path `
        $repoRoot `
        ".env"
}
else {
    $environmentOverride = (
        $environmentOverride.Trim()
    )

    if (
        -not (
            Test-TodobaAbsoluteWindowsPath `
                -Path $environmentOverride
        )
    ) {
        throw (
            "TODOBA_ENV_FILE must be an absolute path."
        )
    }

    $environmentPath = (
        [System.IO.Path]::GetFullPath(
            $environmentOverride
        )
    )

    $env:TODOBA_ENV_FILE = $environmentPath
}

$telegramSessionOverride = (
    [Environment]::GetEnvironmentVariable(
        "TELEGRAM_SESSION"
    )
)

if (
    [string]::IsNullOrWhiteSpace(
        $telegramSessionOverride
    )
) {
    $telegramSessionIdentifier = Join-Path `
        $repoRoot `
        "todoba"

    $telegramSessionPath = $telegramSessionIdentifier + ".session"
}
else {
    $telegramSessionOverride = (
        $telegramSessionOverride.Trim()
    )

    if (
        -not (
            Test-TodobaAbsoluteWindowsPath `
                -Path $telegramSessionOverride
        )
    ) {
        throw (
            "TELEGRAM_SESSION must be an absolute path."
        )
    }

    $telegramSessionIdentifier = (
        [System.IO.Path]::GetFullPath(
            $telegramSessionOverride
        )
    )

    if (
        $telegramSessionIdentifier.EndsWith(
            ".session",
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        $telegramSessionPath = (
            $telegramSessionIdentifier
        )
    }
    else {
                $telegramSessionPath = $telegramSessionIdentifier + ".session"
    }

    $env:TELEGRAM_SESSION = (
        $telegramSessionIdentifier
    )
}

$apiEntryPath = Join-Path `
$repoRoot `
"backend\start_api.py"

$executorEntryPath = Join-Path `
$repoRoot `
"backend\start_executor.py"

$packageBuilderEntryPath = Join-Path `
$repoRoot `
"backend\start_package_builder.py"

$logRootOverride = (
    [Environment]::GetEnvironmentVariable(
        "TODOBA_RUNTIME_LOG_ROOT"
    )
)

if (
    [string]::IsNullOrWhiteSpace(
        $logRootOverride
    )
) {
    $logDirectory = Join-Path `
        $repoRoot `
        "data\runtime_logs"
}
else {
    $logRootOverride = (
        $logRootOverride.Trim()
    )

    if (
        -not (
            Test-TodobaAbsoluteWindowsPath `
                -Path $logRootOverride
        )
    ) {
        throw (
            "TODOBA_RUNTIME_LOG_ROOT must be an absolute path."
        )
    }

    $logDirectory = (
        [System.IO.Path]::GetFullPath(
            $logRootOverride
        )
    )

    $env:TODOBA_RUNTIME_LOG_ROOT = $logDirectory
}

$env:TODOBA_RUNTIME_MODE = "CLOUD"
$env:TELEGRAM_EXECUTION_MODE = "REMOTE_VPS"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"


$requiredPaths = [ordered]@{
    Python = $pythonPath
    Environment = $environmentPath
    TelegramSession = $telegramSessionPath
    ApiEntry = $apiEntryPath
    ExecutorEntry = $executorEntryPath
    PackageBuilderEntry = $packageBuilderEntryPath
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
    Write-Output "RELEASE_ROOT=$releaseRoot"
    Write-Output "PYTHON_PATH=$pythonPath"
    Write-Output "ENVIRONMENT_PATH=$environmentPath"
    Write-Output "LOG_DIRECTORY=$logDirectory"
    Write-Output "TELEGRAM_SESSION_FILE=$telegramSessionPath"
    Write-Output "API_MODULE=backend.start_api"
    Write-Output "EXECUTOR_MODULE=backend.start_executor"
    Write-Output "PACKAGE_BUILDER_MODULE=backend.start_package_builder"

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
    },
    [PSCustomObject]@{
        Name = "package-builder"
        Module = "backend.start_package_builder"
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