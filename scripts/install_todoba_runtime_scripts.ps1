param(
    [Parameter(Mandatory = $true)]
    [string]$SourceReleaseRoot,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeRoot,

    [switch]$ValidateOnly
)

# TODOBA Stable Runtime Script Installer
#
# Owns:
# - initial installation of stable launcher/controller pair
# - byte/hash equivalence with explicit source release
#
# Does NOT own:
# - Scheduled Task registration/rebinding
# - process lifecycle
# - persistent environment
# - release switching
# - Python runtime provisioning

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


$SourceReleaseRoot = $SourceReleaseRoot.Trim()
$RuntimeRoot = $RuntimeRoot.Trim()

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $SourceReleaseRoot
)) {
    throw "SourceReleaseRoot must be an absolute path."
}

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $RuntimeRoot
)) {
    throw "RuntimeRoot must be an absolute path."
}

$resolvedSourceReleaseRoot = (
    [System.IO.Path]::GetFullPath(
        $SourceReleaseRoot
    )
)

$resolvedRuntimeRoot = (
    [System.IO.Path]::GetFullPath(
        $RuntimeRoot
    )
)

if (-not (
    Test-Path `
        -LiteralPath $resolvedSourceReleaseRoot `
        -PathType Container
)) {
    throw "SourceReleaseRoot does not exist."
}

$sourceLauncher = Join-Path `
    $resolvedSourceReleaseRoot `
    "scripts\start_todoba.ps1"

$sourceController = Join-Path `
    $resolvedSourceReleaseRoot `
    "scripts\control_todoba.ps1"

if (-not (
    Test-Path `
        -LiteralPath $sourceLauncher `
        -PathType Leaf
)) {
    throw "Source runtime launcher does not exist."
}

if (-not (
    Test-Path `
        -LiteralPath $sourceController `
        -PathType Leaf
)) {
    throw "Source runtime controller does not exist."
}

if (
    Test-Path `
        -LiteralPath $resolvedRuntimeRoot
) {
    throw "RuntimeRoot already exists."
}

$sourceLauncherHash = (
    Get-FileHash `
        -LiteralPath $sourceLauncher `
        -Algorithm SHA256
).Hash

$sourceControllerHash = (
    Get-FileHash `
        -LiteralPath $sourceController `
        -Algorithm SHA256
).Hash

if ($ValidateOnly) {

    Write-Output (
        "TODOBA_RUNTIME_SCRIPT_INSTALLATION_VALIDATION=PASS"
    )

    Write-Output "SOURCE_RELEASE_ROOT=$resolvedSourceReleaseRoot"
    Write-Output "RUNTIME_ROOT=$resolvedRuntimeRoot"
    Write-Output "SCRIPT_COUNT=2"
    Write-Output "LAUNCHER_SHA256=$sourceLauncherHash"
    Write-Output "CONTROLLER_SHA256=$sourceControllerHash"
    Write-Output "FILESYSTEM_MUTATION=NONE"

    exit 0
}


$parentRoot = Split-Path `
    -Parent `
    $resolvedRuntimeRoot

$tempRoot = (
    $resolvedRuntimeRoot +
    ".installing-" +
    [guid]::NewGuid().ToString("N")
)

$published = $false

try {

    if (-not (
        Test-Path `
            -LiteralPath $parentRoot `
            -PathType Container
    )) {
        New-Item `
            -ItemType Directory `
            -Path $parentRoot `
            -Force |
        Out-Null
    }

    New-Item `
        -ItemType Directory `
        -Path $tempRoot |
    Out-Null

    $tempLauncher = Join-Path `
        $tempRoot `
        "start_todoba.ps1"

    $tempController = Join-Path `
        $tempRoot `
        "control_todoba.ps1"

    Copy-Item `
        -LiteralPath $sourceLauncher `
        -Destination $tempLauncher

    Copy-Item `
        -LiteralPath $sourceController `
        -Destination $tempController

    $tempLauncherHash = (
        Get-FileHash `
            -LiteralPath $tempLauncher `
            -Algorithm SHA256
    ).Hash

    $tempControllerHash = (
        Get-FileHash `
            -LiteralPath $tempController `
            -Algorithm SHA256
    ).Hash

    if ($tempLauncherHash -cne $sourceLauncherHash) {
        throw "Launcher SHA256 verification failed."
    }

    if ($tempControllerHash -cne $sourceControllerHash) {
        throw "Controller SHA256 verification failed."
    }

    [System.IO.Directory]::Move(
        $tempRoot,
        $resolvedRuntimeRoot
    )

    $published = $true

    $installedLauncher = Join-Path `
        $resolvedRuntimeRoot `
        "start_todoba.ps1"

    $installedController = Join-Path `
        $resolvedRuntimeRoot `
        "control_todoba.ps1"

    $installedFiles = @(
        Get-ChildItem `
            -LiteralPath $resolvedRuntimeRoot `
            -File
    )

    if ($installedFiles.Count -ne 2) {
        throw "Installed runtime script count mismatch."
    }

    $installedNames = @(
        $installedFiles.Name |
        Sort-Object
    )

    $expectedNames = @(
        "control_todoba.ps1",
        "start_todoba.ps1"
    )

    $nameDifferences = @(
        Compare-Object `
            $expectedNames `
            $installedNames
    )

    if ($nameDifferences.Count -ne 0) {
        throw "Installed runtime script set mismatch."
    }

    $installedLauncherHash = (
        Get-FileHash `
            -LiteralPath $installedLauncher `
            -Algorithm SHA256
    ).Hash

    $installedControllerHash = (
        Get-FileHash `
            -LiteralPath $installedController `
            -Algorithm SHA256
    ).Hash

    if ($installedLauncherHash -cne $sourceLauncherHash) {
        throw "Published launcher SHA256 verification failed."
    }

    if ($installedControllerHash -cne $sourceControllerHash) {
        throw "Published controller SHA256 verification failed."
    }
}
catch {

    if (
        -not $published -and
        (
            Test-Path `
                -LiteralPath $tempRoot
        )
    ) {
        Remove-Item `
            -LiteralPath $tempRoot `
            -Recurse `
            -Force `
            -ErrorAction SilentlyContinue
    }

    throw
}


Write-Output "TODOBA_RUNTIME_SCRIPTS_INSTALLED=TRUE"
Write-Output "RUNTIME_ROOT=$resolvedRuntimeRoot"
Write-Output "SCRIPT_COUNT=2"
Write-Output "LAUNCHER_PATH=$installedLauncher"
Write-Output "CONTROLLER_PATH=$installedController"
Write-Output "LAUNCHER_SHA256=$installedLauncherHash"
Write-Output "CONTROLLER_SHA256=$installedControllerHash"
Write-Output "TASK_MUTATION=NONE"
Write-Output "PROCESS_MUTATION=NONE"
Write-Output "ENVIRONMENT_MUTATION=NONE"
Write-Output "RELEASE_SWITCH_MUTATION=NONE"

