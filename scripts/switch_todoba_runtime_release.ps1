param(
    [Parameter(Mandatory = $true)]
    [string]$InstallRoot,

    [Parameter(Mandatory = $true)]
    [string]$TargetReleaseId,

    [switch]$ValidateOnly
)

# TODOBA Controlled Runtime Release Switcher
#
# Owns:
# - verification of one already-installed target release
# - controlled transition of the existing "current" NTFS junction
# - explicit rollback by invoking the same operation with a previous release id
#
# Does NOT own:
# - release installation/copying
# - runtime process start/stop/restart
# - Scheduled Task registration/rebinding
# - persistent environment authority
# - Python runtime provisioning
# - stable runtime script installation

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


function Get-TodobaJunctionTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $item = Get-Item `
        -LiteralPath $Path `
        -Force `
        -ErrorAction Stop

    if (
        -not (
            $item.Attributes `
            -band `
            [System.IO.FileAttributes]::ReparsePoint
        )
    ) {
        throw "Current release path is not a reparse-point junction."
    }

    if ($null -eq $item.Target) {
        throw "Current junction target is unavailable."
    }

    $target = @(
        $item.Target
    )

    if ($target.Count -ne 1) {
        throw "Current junction target is ambiguous."
    }

    return (
        [System.IO.Path]::GetFullPath(
            [string]$target[0]
        )
    )
}


$InstallRoot = $InstallRoot.Trim()
$TargetReleaseId = $TargetReleaseId.Trim()

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $InstallRoot
)) {
    throw "InstallRoot must be an absolute path."
}

if (
    $TargetReleaseId -notmatch '^[0-9a-f]{40}$'
) {
    throw "TargetReleaseId must be one full lowercase Git SHA."
}

$resolvedInstallRoot = (
    [System.IO.Path]::GetFullPath(
        $InstallRoot
    )
)

$releasesRootCandidate = Join-Path `
    $resolvedInstallRoot `
    "releases"

$releasesRoot = (
    [System.IO.Path]::GetFullPath(
        $releasesRootCandidate
    )
)

$currentPathCandidate = Join-Path `
    $resolvedInstallRoot `
    "current"

$currentPath = (
    [System.IO.Path]::GetFullPath(
        $currentPathCandidate
    )
)

$targetReleaseCandidate = Join-Path `
    $releasesRoot `
    $TargetReleaseId

$targetReleasePath = (
    [System.IO.Path]::GetFullPath(
        $targetReleaseCandidate
    )
)

if (-not (
    Test-Path `
        -LiteralPath $targetReleasePath `
        -PathType Container
)) {
    throw "Target installed release does not exist."
}

if (-not (
    Test-Path `
        -LiteralPath $currentPath
)) {
    throw "Current release path does not exist."
}

$currentTarget = Get-TodobaJunctionTarget `
    -Path $currentPath

$trimmedReleasesRoot = $releasesRoot.TrimEnd(
    '\',
    '/'
)

$releasesPrefix = (
    $trimmedReleasesRoot +
    [System.IO.Path]::DirectorySeparatorChar
)

if (-not (
    $currentTarget.StartsWith(
        $releasesPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )
)) {
    throw "Current junction target is outside installed release authority."
}

$currentReleaseId = Split-Path `
    -Leaf `
    $currentTarget

if (
    $currentReleaseId -notmatch '^[0-9a-f]{40}$'
) {
    throw "Current junction target is not a valid installed release identity."
}

$currentReleaseCandidate = Join-Path `
    $releasesRoot `
    $currentReleaseId

$currentReleasePath = (
    [System.IO.Path]::GetFullPath(
        $currentReleaseCandidate
    )
)

if (-not (
    [string]::Equals(
        $currentTarget.TrimEnd('\', '/'),
        $currentReleasePath.TrimEnd('\', '/'),
        [System.StringComparison]::OrdinalIgnoreCase
    )
)) {
    throw "Current junction target is outside installed release authority."
}

$verifiedCurrentId = Test-TodobaReleaseIntegrity `
    -Root $currentReleasePath

if ($verifiedCurrentId -ne $currentReleaseId) {
    throw "Current installed release identity verification failed."
}

$verifiedTargetId = Test-TodobaReleaseIntegrity `
    -Root $targetReleasePath

if ($verifiedTargetId -ne $TargetReleaseId) {
    throw "Target installed release identity verification failed."
}

if ($ValidateOnly) {

    Write-Output "TODOBA_RUNTIME_RELEASE_SWITCH_VALIDATION=PASS"
    Write-Output "INSTALL_ROOT=$resolvedInstallRoot"
    Write-Output "CURRENT_PATH=$currentPath"
    Write-Output "CURRENT_RELEASE_ID=$currentReleaseId"
    Write-Output "TARGET_RELEASE_ID=$TargetReleaseId"
    Write-Output "TARGET_RELEASE_PATH=$targetReleasePath"
    Write-Output "CURRENT_POINTER_TYPE=NTFS_JUNCTION"
    Write-Output "FILESYSTEM_MUTATION=NONE"

    exit 0
}

if ($currentReleaseId -eq $TargetReleaseId) {
    throw "Target release is already current."
}

$temporaryCurrentPath = (
    $currentPath +
    ".switching-" +
    [System.Guid]::NewGuid().ToString("N")
)

if (
    Test-Path `
        -LiteralPath $temporaryCurrentPath
) {
    throw "Temporary current junction path already exists."
}

$tempCreated = $false
$oldRemoved = $false

try {

    New-Item `
        -ItemType Junction `
        -Path $temporaryCurrentPath `
        -Target $targetReleasePath `
        -ErrorAction Stop |
    Out-Null

    $tempCreated = $true

    $temporaryTarget = Get-TodobaJunctionTarget `
        -Path $temporaryCurrentPath

    if (-not (
        [string]::Equals(
            $temporaryTarget.TrimEnd('\', '/'),
            $targetReleasePath.TrimEnd('\', '/'),
            [System.StringComparison]::OrdinalIgnoreCase
        )
    )) {
        throw "Temporary current junction target verification failed."
    }

    $temporaryVersion = (
        Get-Content `
            -LiteralPath (
                Join-Path `
                    $temporaryCurrentPath `
                    "VERSION"
            ) `
            -Raw `
            -ErrorAction Stop
    ).Trim()

    if ($temporaryVersion -ne $TargetReleaseId) {
        throw "Temporary current junction release verification failed."
    }

    [System.IO.Directory]::Delete(
        $currentPath
    )

    $oldRemoved = $true

    [System.IO.Directory]::Move(
        $temporaryCurrentPath,
        $currentPath
    )

    $tempCreated = $false

    $finalTarget = Get-TodobaJunctionTarget `
        -Path $currentPath

    if (-not (
        [string]::Equals(
            $finalTarget.TrimEnd('\', '/'),
            $targetReleasePath.TrimEnd('\', '/'),
            [System.StringComparison]::OrdinalIgnoreCase
        )
    )) {
        throw "Current junction target verification failed after switch."
    }

    $finalVersion = (
        Get-Content `
            -LiteralPath (
                Join-Path `
                    $currentPath `
                    "VERSION"
            ) `
            -Raw `
            -ErrorAction Stop
    ).Trim()

    if ($finalVersion -ne $TargetReleaseId) {
        throw "Current release verification failed after switch."
    }
}
catch {

    $originalError = $_

    if (
        $oldRemoved -and
        -not (
            Test-Path `
                -LiteralPath $currentPath
        )
    ) {
        try {
            New-Item `
                -ItemType Junction `
                -Path $currentPath `
                -Target $currentReleasePath `
                -ErrorAction Stop |
            Out-Null
        }
        catch {
            # Best-effort restoration only.
        }
    }

    if (
        $tempCreated -and
        (
            Test-Path `
                -LiteralPath $temporaryCurrentPath
        )
    ) {
        try {
            [System.IO.Directory]::Delete(
                $temporaryCurrentPath
            )
        }
        catch {
            # Best-effort temporary junction cleanup only.
        }
    }

    throw $originalError
}


Write-Output "TODOBA_RUNTIME_RELEASE_SWITCHED=TRUE"
Write-Output "INSTALL_ROOT=$resolvedInstallRoot"
Write-Output "CURRENT_PATH=$currentPath"
Write-Output "PREVIOUS_RELEASE_ID=$currentReleaseId"
Write-Output "CURRENT_RELEASE_ID=$TargetReleaseId"
Write-Output "CURRENT_POINTER_TYPE=NTFS_JUNCTION"
Write-Output "TASK_MUTATION=NONE"
Write-Output "PROCESS_MUTATION=NONE"
Write-Output "ENVIRONMENT_MUTATION=NONE"
Write-Output "RELEASE_INSTALLATION_MUTATION=NONE"
