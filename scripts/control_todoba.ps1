param(
    [ValidateSet(
        "Status",
        "Start",
        "Stop",
        "Restart"
    )]
    [string]$Action = "Status",

    [ValidateRange(5, 120)]
    [int]$TimeoutSeconds = 30
)

# TODOBA Windows Runtime Controller
#
# Owns:
# - runtime status inspection
# - controlled runtime startup
# - controlled runtime shutdown
# - controlled runtime restart
#
# It does not supervise runtime children,
# execute trading orders, or manage Cloudflared.

Set-StrictMode -Version Latest

$ErrorActionPreference = "Stop"

$taskName = "TODOBA Runtime"


function Test-TodobaAdministrator {
    $identity = (
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )

    $principal = New-Object `
    Security.Principal.WindowsPrincipal(
        $identity
    )

    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}


function Assert-TodobaAdministrator {
    if (-not (Test-TodobaAdministrator)) {
        throw "This action requires an Administrator PowerShell."
    }
}


function Get-TodobaRuntimeProcesses {
    return @(
        Get-CimInstance `
        Win32_Process `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $isPython = (
                $_.Name -eq "python.exe"
            ) -or (
                $_.Name -eq "pythonw.exe"
            )

            $isTodobaRuntime = $false

            if ($null -ne $_.CommandLine) {
                $isTodobaRuntime = (
                    $_.CommandLine -match `
                    "-m\s+backend\.start_(api|executor)(\s|$)"
                )
            }

            $isPython -and $isTodobaRuntime
        }
    )
}


function Get-TodobaStartupSupervisorProcesses {
    $startupScriptPath = (
        Join-Path `
        $PSScriptRoot `
        "start_todoba.ps1"
    )

    $startupScriptPattern = (
        [regex]::Escape(
            $startupScriptPath
        )
    )

    return @(
        Get-CimInstance `
        Win32_Process `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $isPowerShell = (
                $_.Name -eq "powershell.exe"
            ) -or (
                $_.Name -eq "pwsh.exe"
            )

            $hasStartupScript = $false

            if ($null -ne $_.CommandLine) {
                $hasStartupScript = (
                    $_.CommandLine -match `
                    $startupScriptPattern
                )
            }

            $isPowerShell -and $hasStartupScript
        }
    )
}


function Get-TodobaRuntimeStatus {
    $task = Get-ScheduledTask `
    -TaskName $taskName `
    -ErrorAction Stop

    $processes = @(
        Get-TodobaRuntimeProcesses
    )

    $supervisors = @(
        Get-TodobaStartupSupervisorProcesses
    )

    $apiProcesses = @(
        $processes |
        Where-Object {
            $_.CommandLine -match `
            "-m\s+backend\.start_api(\s|$)"
        }
    )

    $executorProcesses = @(
        $processes |
        Where-Object {
            $_.CommandLine -match `
            "-m\s+backend\.start_executor(\s|$)"
        }
    )

    $listener = Get-NetTCPConnection `
    -LocalPort 8000 `
    -State Listen `
    -ErrorAction SilentlyContinue

    return [PSCustomObject]@{
        TaskName = $task.TaskName
        TaskState = $task.State.ToString()
        TaskUser = $task.Principal.UserId
        SupervisorProcessCount = (
            $supervisors.Count
        )
        RuntimeProcessCount = $processes.Count
        ApiProcessCount = $apiProcesses.Count
        ExecutorProcessCount = (
            $executorProcesses.Count
        )
        Port8000Listening = (
            $null -ne $listener
        )
    }
}


function Wait-TodobaTaskState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExpectedState
    )

    $deadline = (
        Get-Date
    ).AddSeconds(
        $TimeoutSeconds
    )

    do {
        $task = Get-ScheduledTask `
        -TaskName $taskName `
        -ErrorAction Stop

        if ($task.State.ToString() -eq $ExpectedState) {
            return
        }

        Start-Sleep `
        -Milliseconds 250
    }
    while (
        (Get-Date) -lt $deadline
    )

    throw "TODOBA Scheduled Task did not reach state $ExpectedState."
}


function Stop-TodobaRuntime {
    Assert-TodobaAdministrator

    $task = Get-ScheduledTask `
    -TaskName $taskName `
    -ErrorAction Stop

    if ($task.State.ToString() -eq "Running") {
        Stop-ScheduledTask `
        -TaskName $taskName
    }

    $supervisors = @(
        Get-TodobaStartupSupervisorProcesses
    )

    foreach ($supervisor in $supervisors) {
        Stop-Process `
        -Id $supervisor.ProcessId `
        -Force `
        -ErrorAction SilentlyContinue
    }

    $targets = @(
        Get-TodobaRuntimeProcesses
    )

    foreach ($target in $targets) {
        Stop-Process `
        -Id $target.ProcessId `
        -Force `
        -ErrorAction SilentlyContinue
    }

    $deadline = (
        Get-Date
    ).AddSeconds(
        $TimeoutSeconds
    )

    $runtimeStopped = $false

    do {
        $task = Get-ScheduledTask `
        -TaskName $taskName `
        -ErrorAction Stop

        $remainingSupervisors = @(
            Get-TodobaStartupSupervisorProcesses
        )

        $remainingProcesses = @(
            Get-TodobaRuntimeProcesses
        )

        $listener = Get-NetTCPConnection `
        -LocalPort 8000 `
        -State Listen `
        -ErrorAction SilentlyContinue

        $runtimeStopped = (
            $task.State.ToString() -eq "Ready" -and
            $remainingSupervisors.Count -eq 0 -and
            $remainingProcesses.Count -eq 0 -and
            $null -eq $listener
        )

        if ($runtimeStopped) {
            break
        }

        Start-Sleep `
        -Milliseconds 250
    }
    while (
        (Get-Date) -lt $deadline
    )

    if (-not $runtimeStopped) {
        throw "TODOBA runtime did not stop cleanly."
    }

    Write-Output "TODOBA_RUNTIME_STOPPED=True"

    Get-TodobaRuntimeStatus
}


function Start-TodobaRuntime {
    Assert-TodobaAdministrator

    $task = Get-ScheduledTask `
    -TaskName $taskName `
    -ErrorAction Stop

    if ($task.State.ToString() -ne "Running") {
        $existingProcesses = @(
            Get-TodobaRuntimeProcesses
        )

        $existingSupervisors = @(
            Get-TodobaStartupSupervisorProcesses
        )

        if (
            $existingProcesses.Count -gt 0 -or
            $existingSupervisors.Count -gt 0
        ) {
            throw "Run Stop before Start because old TODOBA processes still exist."
        }

        Start-ScheduledTask `
        -TaskName $taskName

        Wait-TodobaTaskState `
        -ExpectedState "Running"
    }

    $deadline = (
        Get-Date
    ).AddSeconds(
        $TimeoutSeconds
    )

    do {
        $status = Get-TodobaRuntimeStatus

        $runtimeReady = (
            $status.TaskState -eq "Running" -and
            $status.ApiProcessCount -gt 0 -and
            $status.ExecutorProcessCount -gt 0 -and
            $status.Port8000Listening
        )

        if ($runtimeReady) {
            break
        }

        Start-Sleep `
        -Milliseconds 500
    }
    while (
        (Get-Date) -lt $deadline
    )

    if (-not $runtimeReady) {
        throw "TODOBA runtime did not become ready."
    }

    Write-Output "TODOBA_RUNTIME_STARTED=True"

    $status
}


switch ($Action) {
    "Status" {
        Get-TodobaRuntimeStatus
    }

    "Start" {
        Start-TodobaRuntime
    }

    "Stop" {
        Stop-TodobaRuntime
    }

    "Restart" {
        Stop-TodobaRuntime
        Start-TodobaRuntime
    }
}