param(
    [Parameter(Mandatory = $true)]
    [string]$ReleasePath,

    [Parameter(Mandatory = $true)]
    [string]$InstallRoot,

    [switch]$ValidateOnly
)

# TODOBA Production Runtime Release Installer
#
# Owns:
# - verification of one D3 production runtime release
# - installation into releases\<full-git-sha>
# - immutable versioned release publication
# - creation of the initial "current" NTFS junction
#
# Does NOT own:
# - release switching after current already exists
# - rollback
# - Scheduled Task registration/rebinding
# - runtime process start/stop
# - persistent environment authorities
# - Python runtime installation
# - shared config/data/session/log state

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


$ReleasePath = $ReleasePath.Trim()
$InstallRoot = $InstallRoot.Trim()

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $ReleasePath
)) {
    throw "ReleasePath must be an absolute path."
}

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $InstallRoot
)) {
    throw "InstallRoot must be an absolute path."
}

$resolvedReleasePath = (
    [System.IO.Path]::GetFullPath(
        $ReleasePath
    )
)

$resolvedInstallRoot = (
    [System.IO.Path]::GetFullPath(
        $InstallRoot
    )
)

if (-not (
    Test-Path `
        -LiteralPath $resolvedReleasePath `
        -PathType Container
)) {
    throw "ReleasePath does not exist."
}

$releaseId = Test-TodobaReleaseIntegrity `
    -Root $resolvedReleasePath

$releasesRoot = Join-Path `
    $resolvedInstallRoot `
    "releases"

$installedReleasePath = Join-Path `
    $releasesRoot `
    $releaseId

$currentPath = Join-Path `
    $resolvedInstallRoot `
    "current"

if (
    Test-Path `
        -LiteralPath $installedReleasePath
) {
    throw "Versioned release already exists."
}

if (
    Test-Path `
        -LiteralPath $currentPath
) {
    throw (
        "Current release path already exists. " +
        "Release switching is owned by a separate capability."
    )
}

if ($ValidateOnly) {

    Write-Output "TODOBA_RUNTIME_RELEASE_INSTALL_VALIDATION=PASS"
    Write-Output "RELEASE_ID=$releaseId"
    Write-Output "SOURCE_RELEASE=$resolvedReleasePath"
    Write-Output "INSTALL_ROOT=$resolvedInstallRoot"
    Write-Output "VERSIONED_RELEASE=$installedReleasePath"
    Write-Output "CURRENT_PATH=$currentPath"
    Write-Output "CURRENT_POINTER_TYPE=NTFS_JUNCTION"
    Write-Output "FILESYSTEM_MUTATION=NONE"

    exit 0
}


$temporaryReleasePath = Join-Path `
    $releasesRoot `
    (
        ".installing-" +
        $releaseId +
        "-" +
        [System.Guid]::NewGuid().ToString("N")
    )

$published = $false
$currentCreated = $false

try {

    New-Item `
        -ItemType Directory `
        -Path $resolvedInstallRoot `
        -Force `
        -ErrorAction Stop |
    Out-Null

    New-Item `
        -ItemType Directory `
        -Path $releasesRoot `
        -Force `
        -ErrorAction Stop |
    Out-Null

    if (
        Test-Path `
            -LiteralPath $temporaryReleasePath
    ) {
        throw "Temporary release installation path already exists."
    }

    New-Item `
        -ItemType Directory `
        -Path $temporaryReleasePath `
        -ErrorAction Stop |
    Out-Null

    Get-ChildItem `
        -LiteralPath $resolvedReleasePath `
        -Force `
        -ErrorAction Stop |
    ForEach-Object {

        Copy-Item `
            -LiteralPath $_.FullName `
            -Destination $temporaryReleasePath `
            -Recurse `
            -Force `
            -ErrorAction Stop
    }

    $copiedReleaseId = Test-TodobaReleaseIntegrity `
        -Root $temporaryReleasePath

    if ($copiedReleaseId -ne $releaseId) {
        throw "Copied release identity changed during installation."
    }

    if (
        Test-Path `
            -LiteralPath $installedReleasePath
    ) {
        throw "Versioned release already exists."
    }

    Move-Item `
        -LiteralPath $temporaryReleasePath `
        -Destination $installedReleasePath `
        -ErrorAction Stop

    $published = $true

    $publishedReleaseId = Test-TodobaReleaseIntegrity `
        -Root $installedReleasePath

    if ($publishedReleaseId -ne $releaseId) {
        throw "Published release identity verification failed."
    }

    if (
        Test-Path `
            -LiteralPath $currentPath
    ) {
        throw (
            "Current release path appeared during installation."
        )
    }

    New-Item `
        -ItemType Junction `
        -Path $currentPath `
        -Target $installedReleasePath `
        -ErrorAction Stop |
    Out-Null

    $currentCreated = $true

    $currentItem = Get-Item `
        -LiteralPath $currentPath `
        -Force `
        -ErrorAction Stop

    if (
        -not (
            $currentItem.Attributes `
            -band `
            [System.IO.FileAttributes]::ReparsePoint
        )
    ) {
        throw "Current path is not a reparse-point junction."
    }

    $currentVersion = (
        Get-Content `
            -LiteralPath (
                Join-Path `
                    $currentPath `
                    "VERSION"
            ) `
            -Raw `
            -ErrorAction Stop
    ).Trim()

    if ($currentVersion -ne $releaseId) {
        throw "Current junction does not resolve to installed release."
    }
}
catch {

    if (
        -not $published -and
        (
            Test-Path `
                -LiteralPath $temporaryReleasePath
        )
    ) {
        Remove-Item `
            -LiteralPath $temporaryReleasePath `
            -Recurse `
            -Force `
            -ErrorAction SilentlyContinue
    }

    if (
        $currentCreated -and
        (
            Test-Path `
                -LiteralPath $currentPath
        )
    ) {
        Remove-Item `
            -LiteralPath $currentPath `
            -Force `
            -ErrorAction SilentlyContinue
    }

    throw
}


Write-Output "TODOBA_RUNTIME_RELEASE_INSTALLED=TRUE"
Write-Output "RELEASE_ID=$releaseId"
Write-Output "VERSIONED_RELEASE=$installedReleasePath"
Write-Output "CURRENT_PATH=$currentPath"
Write-Output "CURRENT_POINTER_TYPE=NTFS_JUNCTION"
Write-Output "TASK_MUTATION=NONE"
Write-Output "PROCESS_MUTATION=NONE"
Write-Output "ENVIRONMENT_MUTATION=NONE"

