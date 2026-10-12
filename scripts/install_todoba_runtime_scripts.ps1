param(
    [Parameter(Mandatory = $true)]
    [string]$InstallRoot,

    [Parameter(Mandatory = $true)]
    [string]$SourceReleaseId,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeRoot,

    [switch]$ValidateOnly
)

# TODOBA Stable Runtime Script Installer
#
# Owns:
# - initial installation of stable launcher/controller pair
# - byte/hash equivalence with one verified installed release
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



function Get-TodobaSha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return (
        Get-FileHash `
            -LiteralPath $Path `
            -Algorithm SHA256 `
            -ErrorAction Stop
    ).Hash.ToLowerInvariant()
}

function Get-TodobaRelativeFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $normalizedRoot = (
        [System.IO.Path]::GetFullPath(
            $Root
        )
    ).TrimEnd(
        '\',
        '/'
    )

    return @(
        Get-ChildItem `
            -LiteralPath $normalizedRoot `
            -Recurse `
            -File `
            -Force `
            -ErrorAction Stop |
        ForEach-Object {
            $_.FullName.Substring(
                $normalizedRoot.Length
            ).TrimStart(
                '\',
                '/'
            ).Replace(
                '\',
                '/'
            )
        } |
        Sort-Object
    )
}

function Test-TodobaReleaseIntegrity {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $versionPath = Join-Path `
        $Root `
        "VERSION"

    $manifestPath = Join-Path `
        $Root `
        "release-manifest.json"

    $sha256Path = Join-Path `
        $Root `
        "SHA256SUMS"

    foreach ($required in @(
        $versionPath,
        $manifestPath,
        $sha256Path
    )) {
        if (-not (
            Test-Path `
                -LiteralPath $required `
                -PathType Leaf
        )) {
            throw (
                "Release metadata is missing: " +
                [System.IO.Path]::GetFileName(
                    $required
                )
            )
        }
    }

    $releaseId = (
        Get-Content `
            -LiteralPath $versionPath `
            -Raw `
            -ErrorAction Stop
    ).Trim()

    if (
        $releaseId -notmatch '^[0-9a-f]{40}$'
    ) {
        throw "VERSION must contain one full lowercase Git SHA."
    }

    try {
        $manifest = (
            Get-Content `
                -LiteralPath $manifestPath `
                -Raw `
                -ErrorAction Stop
        ) | ConvertFrom-Json `
            -ErrorAction Stop
    }
    catch {
        throw "release-manifest.json is invalid."
    }

    if ($manifest.schema_version -ne 1) {
        throw "Unsupported release manifest schema."
    }

    if ($manifest.release_id -ne $releaseId) {
        throw "Release manifest identity does not match VERSION."
    }

    $entries = @(
        $manifest.files
    )

    if ($entries.Count -eq 0) {
        throw "Release manifest has no files."
    }

    $manifestPaths = @()

    foreach ($entry in $entries) {

        $relativePath = [string]$entry.path

        if (
            [string]::IsNullOrWhiteSpace(
                $relativePath
            )
        ) {
            throw "Release manifest contains an empty path."
        }

        $relativePath = $relativePath.Replace(
            '\',
            '/'
        )

        if (
            [System.IO.Path]::IsPathRooted(
                $relativePath
            ) -or
            $relativePath.StartsWith(
                "../"
            ) -or
            $relativePath.Contains(
                "/../"
            )
        ) {
            throw "Release manifest contains an unsafe path."
        }

        $manifestPaths += $relativePath

        $payloadPath = Join-Path `
            $Root `
            ($relativePath.Replace(
                '/',
                '\'
            ))

        if (-not (
            Test-Path `
                -LiteralPath $payloadPath `
                -PathType Leaf
        )) {
            throw (
                "Release payload is missing: " +
                $relativePath
            )
        }

        $item = Get-Item `
            -LiteralPath $payloadPath `
            -ErrorAction Stop

        if (
            [int64]$item.Length -ne
            [int64]$entry.size
        ) {
            throw (
                "Release payload size mismatch: " +
                $relativePath
            )
        }

        $actualHash = Get-TodobaSha256 `
            -Path $payloadPath

        $expectedHash = (
            [string]$entry.sha256
        ).ToLowerInvariant()

        if ($actualHash -ne $expectedHash) {
            throw (
                "Release payload SHA256 mismatch: " +
                $relativePath
            )
        }
    }

    $sortedManifestPaths = @(
        $manifestPaths
    )

    [System.Array]::Sort(
        $sortedManifestPaths,
        [System.StringComparer]::Ordinal
    )

    if (
        (
            $manifestPaths -join "`n"
        ) -cne (
            $sortedManifestPaths -join "`n"
        )
    ) {
        throw "Release manifest paths are not sorted."
    }

    $uniqueManifestPaths = @(
        $manifestPaths |
        Sort-Object -Unique
    )

    if (
        $uniqueManifestPaths.Count -ne
        $manifestPaths.Count
    ) {
        throw "Release manifest contains duplicate paths."
    }

    $expectedShaLines = @(
        foreach ($entry in $entries) {
            (
                ([string]$entry.sha256).ToLowerInvariant() +
                "  " +
                ([string]$entry.path).Replace(
                    '\',
                    '/'
                )
            )
        }
    )

    $actualShaLines = @(
        Get-Content `
            -LiteralPath $sha256Path `
            -ErrorAction Stop
    )

    if (
        (
            $actualShaLines -join "`n"
        ) -ne (
            $expectedShaLines -join "`n"
        )
    ) {
        throw "SHA256SUMS does not match release manifest."
    }

    $actualFiles = @(
        Get-TodobaRelativeFiles `
            -Root $Root
    )

    $expectedFiles = @(
        (
            $manifestPaths +
            @(
                "release-manifest.json",
                "SHA256SUMS"
            )
        ) |
        Sort-Object -Unique
    )

    if (
        (
            $actualFiles -join "`n"
        ) -ne (
            $expectedFiles -join "`n"
        )
    ) {
        throw "Release contains files outside its manifest authority."
    }

    return $releaseId
}


$InstallRoot = $InstallRoot.Trim()
$SourceReleaseId = $SourceReleaseId.Trim()
$RuntimeRoot = $RuntimeRoot.Trim()

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $InstallRoot
)) {
    throw "InstallRoot must be an absolute path."
}

if (
    $SourceReleaseId -notmatch '^[0-9a-f]{40}$'
) {
    throw "SourceReleaseId must be one full lowercase Git SHA."
}

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $RuntimeRoot
)) {
    throw "RuntimeRoot must be an absolute path."
}

$resolvedInstallRoot = (
    [System.IO.Path]::GetFullPath(
        $InstallRoot
    )
)

$resolvedRuntimeRoot = (
    [System.IO.Path]::GetFullPath(
        $RuntimeRoot
    )
)

$releasesRoot = Join-Path `
    $resolvedInstallRoot `
    "releases"

$sourceReleaseCandidate = Join-Path `
    $releasesRoot `
    $SourceReleaseId

$sourceReleasePath = (
    [System.IO.Path]::GetFullPath(
        $sourceReleaseCandidate
    )
)

$releasesPrefix = (
    $releasesRoot.TrimEnd('\', '/') +
    [System.IO.Path]::DirectorySeparatorChar
)

if (-not (
    $sourceReleasePath.StartsWith(
        $releasesPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )
)) {
    throw "Source release is outside installed release authority."
}

if (-not (
    Test-Path `
        -LiteralPath $sourceReleasePath `
        -PathType Container
)) {
    throw "Source installed release does not exist."
}

# Reject junction/symlink redirection in installed release authority.
$authorityItemPath = $sourceReleasePath

while ($true) {
    $authorityItem = Get-Item `
        -LiteralPath $authorityItemPath `
        -Force `
        -ErrorAction Stop

    if (
        $authorityItem.Attributes -band
        [System.IO.FileAttributes]::ReparsePoint
    ) {
        throw "Installed release authority contains a reparse point."
    }

    $authorityParent = [System.IO.Path]::GetDirectoryName(
        $authorityItemPath.TrimEnd('\', '/')
    )

    if (
        [string]::IsNullOrEmpty($authorityParent) -or
        $authorityParent -eq $authorityItemPath
    ) {
        break
    }

    $authorityItemPath = $authorityParent
}

$verifiedSourceReleaseId = Test-TodobaReleaseIntegrity `
    -Root $sourceReleasePath

if ($verifiedSourceReleaseId -ne $SourceReleaseId) {
    throw "Source installed release identity verification failed."
}

$sourceLauncher = Join-Path `
    $sourceReleasePath `
    "scripts\start_todoba.ps1"

$sourceController = Join-Path `
    $sourceReleasePath `
    "scripts\control_todoba.ps1"

if (-not (
    Test-Path `
        -LiteralPath $sourceLauncher `
        -PathType Leaf
)) {
    throw "Verified release does not contain runtime launcher."
}

if (-not (
    Test-Path `
        -LiteralPath $sourceController `
        -PathType Leaf
)) {
    throw "Verified release does not contain runtime controller."
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

    Write-Output "SOURCE_RELEASE_ROOT=$sourceReleasePath"
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

