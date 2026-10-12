from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

BUILDER = (
    ROOT
    / "scripts"
    / "build_todoba_runtime_release.py"
)

EXPECTED_RUNTIME_SCRIPTS = {
    "scripts/build_trusted_agent_deployment.py",
    "scripts/process_customer_deployment_package_build_requests.py",
    "scripts/provision_trusted_agent_deployment.py",
    "scripts/trusted_agent_metaeditor_compiler_runner.py",
    "scripts/start_todoba.ps1",
    "scripts/control_todoba.ps1",
    "scripts/provision_todoba_runtime_task.ps1",
}

EXPECTED_MQL5_FILES = {
    "MQL5/Experts/TODOBA_Trusted_Agent.mq5",
    "MQL5/Include/TODOBAControl/ControlEngine.mqh",
    "MQL5/Include/TODOBAControl/ControlMissionParser.mqh",
    "MQL5/Include/TODOBAControl/ControlMissionSignatureVerifier.mqh",
    "MQL5/Include/TODOBAControl/ControlMissionSigningPayload.mqh",
    "MQL5/Include/TODOBAControl/ControlMissionValidator.mqh",
    "MQL5/Include/TODOBAControl/ControlPermissionGuard.mqh",
    "MQL5/Include/TODOBAControl/ControlResult.mqh",
    "MQL5/Include/TODOBAExecution/AccountFingerprint.mqh",
    "MQL5/Include/TODOBAExecution/BrokerStateReader.mqh",
    "MQL5/Include/TODOBAExecution/ExecutionEngine.mqh",
    "MQL5/Include/TODOBAExecution/ExecutionMissionParser.mqh",
    "MQL5/Include/TODOBAExecution/ExecutionMissionSignatureVerifier.mqh",
    "MQL5/Include/TODOBAExecution/ExecutionMissionSigningPayload.mqh",
    "MQL5/Include/TODOBAExecution/ExecutionMissionState.mqh",
    "MQL5/Include/TODOBAExecution/ExecutionMissionValidator.mqh",
    "MQL5/Include/TODOBAExecution/ExecutionPermissionGuard.mqh",
    "MQL5/Include/TODOBAExecution/ExecutionResult.mqh",
    "MQL5/Include/TODOBAExecution/ExecutionSafetyGuard.mqh",
    "MQL5/Include/TODOBAExecution/MissionFreshnessGuard.mqh",
    "MQL5/Include/TODOBAExecution/SymbolMapper.mqh",
}

GENERATED_RELEASE_FILES = {
    "VERSION",
    "release-manifest.json",
    "SHA256SUMS",
}


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    return completed.stdout.strip()


def _head() -> str:
    return _git(
        "rev-parse",
        "HEAD",
    )


def _tracked_backend_python() -> set[str]:
    output = _git(
        "ls-files",
        "backend",
    )

    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip().endswith(".py")
    }


def _expected_payload_files() -> set[str]:
    return (
        _tracked_backend_python()
        | {
            "backend/brain/identity.md",
            "requirements-production.txt",
        }
        | EXPECTED_RUNTIME_SCRIPTS
        | EXPECTED_MQL5_FILES
    )


def _require_builder() -> None:
    assert BUILDER.is_file(), (
        "Production runtime release builder "
        "does not exist."
    )


def _build_release(
    tmp_path: Path,
) -> Path:
    _require_builder()

    output_root = (
        tmp_path
        / "runtime-releases"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--output-root",
            str(output_root),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, (
        completed.stdout
        + "\n"
        + completed.stderr
    )

    release_root = (
        output_root
        / _head()
    )

    assert release_root.is_dir()

    return release_root


def _release_files(
    release_root: Path,
) -> set[str]:
    return {
        path.relative_to(
            release_root
        ).as_posix()
        for path in release_root.rglob("*")
        if path.is_file()
    }


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def test_runtime_release_builder_exists() -> None:
    _require_builder()


def test_runtime_release_contains_exact_locked_source_boundary(
    tmp_path: Path,
) -> None:
    release_root = _build_release(
        tmp_path
    )

    expected = (
        _expected_payload_files()
        | GENERATED_RELEASE_FILES
    )

    assert (
        _release_files(
            release_root
        )
        == expected
    )


def test_runtime_release_excludes_dev_secret_and_proof_material(
    tmp_path: Path,
) -> None:
    release_root = _build_release(
        tmp_path
    )

    files = _release_files(
        release_root
    )

    forbidden_fragments = (
        "tests/",
        ".git/",
        ".venv/",
        "data/",
        "pytest-runtime/",
        "__pycache__/",
        ".env",
        ".session",
        "requirements.txt",
        "TODOBA_Proof",
        "TODOBAAgentCredentials.mqh",
        "build_customer_setup_windows.py",
        "build_customer_vps_connect_windows.py",
        "build_customer_setup_packaging_proof.py",
    )

    for path in files:
        for fragment in forbidden_fragments:
            assert fragment not in path


def test_runtime_release_version_is_full_head_sha(
    tmp_path: Path,
) -> None:
    release_root = _build_release(
        tmp_path
    )

    assert (
        (
            release_root
            / "VERSION"
        )
        .read_text(
            encoding="utf-8-sig"
        )
        .strip()
        == _head()
    )


def test_runtime_release_manifest_is_deterministic_and_complete(
    tmp_path: Path,
) -> None:
    release_root = _build_release(
        tmp_path
    )

    manifest_path = (
        release_root
        / "release-manifest.json"
    )

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8-sig"
        )
    )

    assert manifest["schema_version"] == 1
    assert manifest["release_id"] == _head()

    entries = manifest["files"]

    assert isinstance(
        entries,
        list,
    )

    manifest_paths = [
        entry["path"]
        for entry in entries
    ]

    # Manifest hashes payload files only.
    assert set(manifest_paths) == (
        _expected_payload_files()
        | {"VERSION"}
    )

    assert manifest_paths == sorted(
        manifest_paths
    )

    for entry in entries:
        path = (
            release_root
            / entry["path"]
        )

        assert path.is_file()

        assert (
            entry["sha256"]
            == _sha256(path)
        )

        assert (
            entry["size"]
            == path.stat().st_size
        )


def test_runtime_release_sha256sums_matches_manifest(
    tmp_path: Path,
) -> None:
    release_root = _build_release(
        tmp_path
    )

    manifest = json.loads(
        (
            release_root
            / "release-manifest.json"
        ).read_text(
            encoding="utf-8-sig"
        )
    )

    expected_lines = [
        (
            entry["sha256"]
            + "  "
            + entry["path"]
        )
        for entry in manifest["files"]
    ]

    actual_lines = (
        (
            release_root
            / "SHA256SUMS"
        )
        .read_text(
            encoding="utf-8-sig"
        )
        .splitlines()
    )

    assert actual_lines == expected_lines


def test_runtime_release_refuses_existing_release_directory(
    tmp_path: Path,
) -> None:
    _require_builder()

    output_root = (
        tmp_path
        / "runtime-releases"
    )

    first = subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--output-root",
            str(output_root),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert first.returncode == 0

    second = subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--output-root",
            str(output_root),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert second.returncode != 0

    release_root = (
        output_root
        / _head()
    )

    assert release_root.is_dir()


def test_runtime_release_builder_requires_absolute_output_root(
    tmp_path: Path,
) -> None:
    _require_builder()

    completed = subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--output-root",
            "relative-runtime-releases",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
