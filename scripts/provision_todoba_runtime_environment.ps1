param(
    [Parameter(Mandatory = $true)]
    [string]$ReleaseRoot,

    [Parameter(Mandatory = $true)]
    [string]$PythonExecutable,

    [Parameter(Mandatory = $true)]
    [string]$EnvironmentFile,

    [Parameter(Mandatory = $true)]
    [string]$TelegramSession,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeLogRoot,

    [switch]$ValidateOnly
)

# TODOBA persistent production runtime environment authority.
#
# Owns exactly five Machine-scope path authorities.
#
# Does not own:
# - Scheduled Task lifecycle
# - runtime process lifecycle
# - release switching
# - Python runtime provisioning
# - secret values

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"


function Test-TodobaAbsoluteWindowsPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ($Path -match '^[A-Za-z]:[\\/]') {
        return $true
    }

    if ($Path -match '^\\\\[^\\/]+[\\/][^\\/]+') {
        return $true
    }

    return $false
}


function Resolve-TodobaAuthorityPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $candidate = $Value.Trim()

    if (-not (
        Test-TodobaAbsoluteWindowsPath `
            -Path $candidate
    )) {
        throw "$Name must be an absolute path."
    }

    return (
        [System.IO.Path]::GetFullPath(
            $candidate
        )
    )
}


$resolvedReleaseRoot = (
    Resolve-TodobaAuthorityPath `
        -Name "ReleaseRoot" `
        -Value $ReleaseRoot
)

$resolvedPythonExecutable = (
    Resolve-TodobaAuthorityPath `
        -Name "PythonExecutable" `
        -Value $PythonExecutable
)

$resolvedEnvironmentFile = (
    Resolve-TodobaAuthorityPath `
        -Name "EnvironmentFile" `
        -Value $EnvironmentFile
)

$resolvedTelegramSession = (
    Resolve-TodobaAuthorityPath `
        -Name "TelegramSession" `
        -Value $TelegramSession
)

$resolvedRuntimeLogRoot = (
    Resolve-TodobaAuthorityPath `
        -Name "RuntimeLogRoot" `
        -Value $RuntimeLogRoot
)


$authorities = [ordered]@{
    "TODOBA_RELEASE_ROOT" = (
        $resolvedReleaseRoot
    )

    "TODOBA_PYTHON_EXECUTABLE" = (
        $resolvedPythonExecutable
    )

    "TODOBA_ENV_FILE" = (
        $resolvedEnvironmentFile
    )

    "TELEGRAM_SESSION" = (
        $resolvedTelegramSession
    )

    "TODOBA_RUNTIME_LOG_ROOT" = (
        $resolvedRuntimeLogRoot
    )
}


if ($ValidateOnly) {

    Write-Output (
        "TODOBA_RUNTIME_ENVIRONMENT_VALIDATION=PASS"
    )

    foreach ($entry in $authorities.GetEnumerator()) {
        Write-Output (
            "{0}={1}" -f `
            $entry.Key,
            $entry.Value
        )
    }

    Write-Output "PERSISTENCE_SCOPE=Machine"
    Write-Output "AUTHORITY_COUNT=5"
    Write-Output "ENVIRONMENT_MUTATION=NONE"

    exit 0
}


$target = (
    [System.EnvironmentVariableTarget]::Machine
)

$previousValues = [ordered]@{}

foreach ($entry in $authorities.GetEnumerator()) {

    $previousValues[$entry.Key] = (
        [System.Environment]::GetEnvironmentVariable(
            $entry.Key,
            $target
        )
    )
}


try {

    foreach ($entry in $authorities.GetEnumerator()) {

        [System.Environment]::SetEnvironmentVariable(
            $entry.Key,
            $entry.Value,
            $target
        )
    }


    foreach ($entry in $authorities.GetEnumerator()) {

        $persisted = (
            [System.Environment]::GetEnvironmentVariable(
                $entry.Key,
                $target
            )
        )

        if (
            -not [string]::Equals(
                $persisted,
                $entry.Value,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            throw (
                "Machine environment verification failed: " +
                $entry.Key
            )
        }
    }
}
catch {

    $originalError = $_

    foreach ($entry in $previousValues.GetEnumerator()) {

        try {
            [System.Environment]::SetEnvironmentVariable(
                $entry.Key,
                $entry.Value,
                $target
            )
        }
        catch {
            # Preserve original provisioning failure.
        }
    }

    throw $originalError
}


Write-Output (
    "TODOBA_RUNTIME_ENVIRONMENT_PROVISIONED=TRUE"
)

foreach ($entry in $authorities.GetEnumerator()) {
    Write-Output (
        "{0}={1}" -f `
        $entry.Key,
        $entry.Value
    )
}

Write-Output "PERSISTENCE_SCOPE=Machine"
Write-Output "AUTHORITY_COUNT=5"
Write-Output "PERSISTED_VERIFICATION=GREEN"
Write-Output "ROLLBACK_ON_FAILURE=ENABLED"
Write-Output "TASK_MUTATION=NONE"
Write-Output "PROCESS_MUTATION=NONE"
Write-Output "RELEASE_SWITCH_MUTATION=NONE"

