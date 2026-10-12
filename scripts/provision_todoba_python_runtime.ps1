param(
    [Parameter(Mandatory = $true)]
    [string]$BasePythonPath,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeRoot,

    [Parameter(Mandatory = $true)]
    [string]$RequirementsPath,

    [switch]$ValidateOnly
)

# TODOBA Isolated Production Python Runtime Provisioner
#
# Owns:
# - explicit base CPython validation
# - isolated venv creation via -m venv
# - production dependency installation via -m pip
# - dependency and import verification
#
# Does NOT own:
# - persistent environment variables
# - release installation/switching
# - Scheduled Task authority
# - TODOBA process lifecycle
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


function Get-TodobaPythonIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonPath
    )

    $probe = @"
import platform
import struct
import sys

print("PYTHON_VERSION=" + sys.version.split()[0])
print(
    "PYTHON_MAJOR_MINOR="
    + str(sys.version_info.major)
    + "."
    + str(sys.version_info.minor)
)
print(
    "PYTHON_IMPLEMENTATION="
    + platform.python_implementation()
)
print(
    "PYTHON_BITS="
    + str(8 * struct.calcsize("P"))
)
"@

    $output = @(
        $probe |
        & $PythonPath - 2>&1
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Python identity probe failed."
    }

    return @(
        $output |
        ForEach-Object {
            [string]$_
        }
    )
}


$BasePythonPath = $BasePythonPath.Trim()
$RuntimeRoot = $RuntimeRoot.Trim()
$RequirementsPath = $RequirementsPath.Trim()

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $BasePythonPath
)) {
    throw "BasePythonPath must be an absolute path."
}

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $RuntimeRoot
)) {
    throw "RuntimeRoot must be an absolute path."
}

if (-not (
    Test-TodobaAbsoluteWindowsPath `
        -Path $RequirementsPath
)) {
    throw "RequirementsPath must be an absolute path."
}

$resolvedBasePython = (
    [System.IO.Path]::GetFullPath(
        $BasePythonPath
    )
)

$resolvedRuntimeRoot = (
    [System.IO.Path]::GetFullPath(
        $RuntimeRoot
    )
)

$resolvedRequirements = (
    [System.IO.Path]::GetFullPath(
        $RequirementsPath
    )
)

if (-not (
    Test-Path `
        -LiteralPath $resolvedBasePython `
        -PathType Leaf
)) {
    throw "BasePythonPath does not exist."
}

if (-not (
    Test-Path `
        -LiteralPath $resolvedRequirements `
        -PathType Leaf
)) {
    throw "RequirementsPath does not exist."
}

if (
    Test-Path `
        -LiteralPath $resolvedRuntimeRoot
) {
    throw "RuntimeRoot already exists."
}

$requirementsLines = @(
    Get-Content `
        -LiteralPath $resolvedRequirements `
        -ErrorAction Stop |
    ForEach-Object {
        $_.Trim()
    } |
    Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and
        -not $_.StartsWith("#")
    }
)

if ($requirementsLines.Count -eq 0) {
    throw "RequirementsPath contains no production dependencies."
}

foreach ($line in $requirementsLines) {
    if ($line -notmatch '^[A-Za-z0-9_.-]+==[^=\s]+$') {
        throw "Production requirements must use exact == pins only."
    }
}

$baseIdentity = @(
    Get-TodobaPythonIdentity `
        -PythonPath $resolvedBasePython
)

if (
    -not (
        $baseIdentity -contains
        "PYTHON_MAJOR_MINOR=3.13"
    )
) {
    throw "Base Python must be CPython 3.13."
}

if (
    -not (
        $baseIdentity -contains
        "PYTHON_IMPLEMENTATION=CPython"
    )
) {
    throw "Base Python must be CPython."
}

if (
    -not (
        $baseIdentity -contains
        "PYTHON_BITS=64"
    )
) {
    throw "Base Python must be 64-bit."
}

$runtimePython = Join-Path `
    $resolvedRuntimeRoot `
    "Scripts\python.exe"

if ($ValidateOnly) {

    Write-Output "TODOBA_PYTHON_RUNTIME_VALIDATION=PASS"

    foreach ($line in $baseIdentity) {
        Write-Output $line
    }

    Write-Output "BASE_PYTHON=$resolvedBasePython"
    Write-Output "RUNTIME_ROOT=$resolvedRuntimeRoot"
    Write-Output "RUNTIME_PYTHON=$runtimePython"
    Write-Output "REQUIREMENTS_PATH=$resolvedRequirements"
    Write-Output "REQUIREMENTS_COUNT=$($requirementsLines.Count)"
    Write-Output "RUNTIME_MUTATION=NONE"

    exit 0
}


try {

    & $resolvedBasePython -m venv $resolvedRuntimeRoot

    if ($LASTEXITCODE -ne 0) {
        throw "Python venv creation failed."
    }

    if (-not (
        Test-Path `
            -LiteralPath $runtimePython `
            -PathType Leaf
    )) {
        throw "Provisioned runtime python.exe is missing."
    }

    $runtimeIdentity = @(
        Get-TodobaPythonIdentity `
            -PythonPath $runtimePython
    )

    if (
        -not (
            $runtimeIdentity -contains
            "PYTHON_MAJOR_MINOR=3.13"
        )
    ) {
        throw "Provisioned Python runtime is not 3.13."
    }

    if (
        -not (
            $runtimeIdentity -contains
            "PYTHON_IMPLEMENTATION=CPython"
        )
    ) {
        throw "Provisioned Python runtime is not CPython."
    }

    if (
        -not (
            $runtimeIdentity -contains
            "PYTHON_BITS=64"
        )
    ) {
        throw "Provisioned Python runtime is not 64-bit."
    }

    & $runtimePython `
        -m pip install `
        --disable-pip-version-check `
        --requirement `
        $resolvedRequirements

    if ($LASTEXITCODE -ne 0) {
        throw "Production dependency installation failed."
    }

    & $runtimePython -m pip check

    if ($LASTEXITCODE -ne 0) {
        throw "Production dependency verification failed."
    }

    $importProbe = @"
modules = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "dotenv",
    "telethon",
    "MetaTrader5",
    "httpx",
    "cryptography",
]

for name in modules:
    __import__(name)

print("PRODUCTION_IMPORT_PROBE=GREEN")
"@

    $importOutput = @(
        $importProbe |
        & $runtimePython - 2>&1
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Production import verification failed."
    }

    if (
        -not (
            $importOutput -contains
            "PRODUCTION_IMPORT_PROBE=GREEN"
        )
    ) {
        throw "Production import proof marker missing."
    }
}
catch {

    if (
        Test-Path `
            -LiteralPath $resolvedRuntimeRoot
    ) {
        Remove-Item `
            -LiteralPath $resolvedRuntimeRoot `
            -Recurse `
            -Force `
            -ErrorAction SilentlyContinue
    }

    throw
}


Write-Output "TODOBA_PYTHON_RUNTIME_PROVISIONED=TRUE"

foreach ($line in $runtimeIdentity) {
    Write-Output $line
}

Write-Output "RUNTIME_ROOT=$resolvedRuntimeRoot"
Write-Output "RUNTIME_PYTHON=$runtimePython"
Write-Output "REQUIREMENTS_PATH=$resolvedRequirements"
Write-Output "REQUIREMENTS_COUNT=$($requirementsLines.Count)"
Write-Output "DEPENDENCY_VERIFICATION=GREEN"
Write-Output "PRODUCTION_IMPORT_PROBE=GREEN"
Write-Output "ENVIRONMENT_MUTATION=NONE"
Write-Output "TASK_MUTATION=NONE"
Write-Output "PROCESS_MUTATION=NONE"
Write-Output "RELEASE_MUTATION=NONE"
