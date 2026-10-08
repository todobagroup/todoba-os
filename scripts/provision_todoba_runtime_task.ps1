param(
    [Parameter(Mandatory = $true)]
    [string]$LauncherPath,

    [switch]$ValidateOnly
)

# TODOBA Windows Runtime Scheduled Task Provisioner
#
# Owns:
# - registration of the "TODOBA Runtime" Scheduled Task
# - binding that task to the stable runtime launcher
# - SYSTEM / ServiceAccount / Highest task authority
# - startup trigger
#
# It does not:
# - start or stop runtime children
# - switch releases
# - execute trading orders
# - own payment or customer authority

Set-StrictMode -Version Latest

$ErrorActionPreference = "Stop"

$taskName = "TODOBA Runtime"


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


function Assert-TodobaAdministrator {
    $identity = (
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )

    $principal = New-Object `
        Security.Principal.WindowsPrincipal(
            $identity
        )

    if (
        -not $principal.IsInRole(
            [Security.Principal.WindowsBuiltInRole]::Administrator
        )
    ) {
        throw "This action requires an Administrator PowerShell."
    }
}


$LauncherPath = $LauncherPath.Trim()

if (
    -not (
        Test-TodobaAbsoluteWindowsPath `
            -Path $LauncherPath
    )
) {
    throw "LauncherPath must be an absolute path."
}

$resolvedLauncherPath = (
    [System.IO.Path]::GetFullPath(
        $LauncherPath
    )
)

if (
    -not (
        Test-Path `
            -LiteralPath $resolvedLauncherPath `
            -PathType Leaf
    )
) {
    throw "LauncherPath does not exist."
}

$workingDirectory = (
    Split-Path `
        -Parent `
        $resolvedLauncherPath
)

$taskExecute = "powershell.exe"

$taskArguments = (
    '-NoProfile ' +
    '-WindowStyle Hidden ' +
    '-ExecutionPolicy Bypass ' +
    '-File "' +
    $resolvedLauncherPath +
    '"'
)


if ($ValidateOnly) {
    Write-Output "TODOBA_RUNTIME_TASK_VALIDATION=PASS"
    Write-Output "TASK_NAME=$taskName"
    Write-Output "TASK_EXECUTE=$taskExecute"
    Write-Output "TASK_ARGUMENTS=$taskArguments"
    Write-Output "TASK_LAUNCHER_PATH=$resolvedLauncherPath"
    Write-Output "TASK_WORKING_DIRECTORY=$workingDirectory"
    Write-Output "TASK_USER=SYSTEM"
    Write-Output "TASK_LOGON_TYPE=ServiceAccount"
    Write-Output "TASK_RUN_LEVEL=Highest"
    Write-Output "TASK_TRIGGER=AtStartup"
    Write-Output "TASK_MUTATION=NONE"

    exit 0
}


Assert-TodobaAdministrator


$action = New-ScheduledTaskAction `
    -Execute $taskExecute `
    -Argument $taskArguments `
    -WorkingDirectory $workingDirectory


$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType "ServiceAccount" `
    -RunLevel "Highest"


$trigger = New-ScheduledTaskTrigger `
    -AtStartup


$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew


Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Principal $principal `
    -Trigger $trigger `
    -Settings $settings `
    -Force `
    | Out-Null


$registered = Get-ScheduledTask `
    -TaskName $taskName `
    -ErrorAction Stop


Write-Output "TODOBA_RUNTIME_TASK_PROVISIONED=TRUE"
Write-Output "TASK_NAME=$taskName"
Write-Output "TASK_STATE=$($registered.State)"
Write-Output "TASK_USER=$($registered.Principal.UserId)"
Write-Output "TASK_EXECUTE=$taskExecute"
Write-Output "TASK_ARGUMENTS=$taskArguments"
Write-Output "TASK_LAUNCHER_PATH=$resolvedLauncherPath"
Write-Output "TASK_WORKING_DIRECTORY=$workingDirectory"
Write-Output "TASK_TRIGGER=AtStartup"
