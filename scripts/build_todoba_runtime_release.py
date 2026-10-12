"""
TODOBA Production Runtime Release Builder.

Builds one immutable, versioned runtime release from the
committed Git HEAD.

Security / release boundaries:
- source payload is read from Git HEAD, never from uncommitted
  working-tree source
- release identity is the full 40-character Git HEAD SHA
- only the locked production runtime source boundary is copied
- no tests, secrets, sessions, mutable data, dev environment,
  proof MQL5 sources, or generated agent credentials
- an existing release directory is never overwritten
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


REPOSITORY_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

PRODUCTION_REQUIREMENTS_PATH = (
    "requirements-production.txt"
)

BACKEND_STATIC_ASSETS = (
    "backend/brain/identity.md",
)

RUNTIME_SCRIPT_FILES = (
    "scripts/build_trusted_agent_deployment.py",
    "scripts/process_customer_deployment_package_build_requests.py",
    "scripts/provision_trusted_agent_deployment.py",
    "scripts/trusted_agent_metaeditor_compiler_runner.py",
    "scripts/start_todoba.ps1",
    "scripts/control_todoba.ps1",
    "scripts/provision_todoba_runtime_task.ps1",
)

MQL5_RUNTIME_FILES = (
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
)

GENERATED_VERSION_PATH = "VERSION"
GENERATED_MANIFEST_PATH = "release-manifest.json"
GENERATED_SHA256_PATH = "SHA256SUMS"

MANIFEST_SCHEMA_VERSION = 1


def _run_git(
    *arguments: str,
    binary: bool = False,
) -> bytes | str:
    completed = subprocess.run(
        [
            "git",
            *arguments,
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=not binary,
    )

    if completed.returncode != 0:
        stderr = (
            completed.stderr
            if isinstance(
                completed.stderr,
                str,
            )
            else completed.stderr.decode(
                "utf-8",
                errors="replace",
            )
        )

        raise RuntimeError(
            "Git command failed: "
            + " ".join(arguments)
            + ": "
            + stderr.strip()
        )

    return completed.stdout


def _head_release_id() -> str:
    raw = _run_git(
        "rev-parse",
        "HEAD",
    )

    if not isinstance(raw, str):
        raise RuntimeError(
            "Unexpected binary Git HEAD output."
        )

    release_id = raw.strip()

    if (
        len(release_id) != 40
        or any(
            character
            not in "0123456789abcdef"
            for character in release_id
        )
    ):
        raise RuntimeError(
            "Git HEAD must be a full lowercase "
            "40-character commit SHA."
        )

    return release_id


def _tracked_backend_python_files() -> tuple[str, ...]:
    raw = _run_git(
        "ls-tree",
        "-r",
        "--name-only",
        "HEAD",
        "--",
        "backend",
    )

    if not isinstance(raw, str):
        raise RuntimeError(
            "Unexpected binary Git tree output."
        )

    paths = sorted(
        line.strip().replace(
            "\\",
            "/",
        )
        for line in raw.splitlines()
        if line.strip().endswith(".py")
    )

    if not paths:
        raise RuntimeError(
            "Committed backend Python source boundary "
            "is empty."
        )

    return tuple(paths)


def _payload_paths() -> tuple[str, ...]:
    paths = set(
        _tracked_backend_python_files()
    )

    paths.add(
        PRODUCTION_REQUIREMENTS_PATH
    )

    paths.update(
        BACKEND_STATIC_ASSETS
    )

    paths.update(
        RUNTIME_SCRIPT_FILES
    )

    paths.update(
        MQL5_RUNTIME_FILES
    )

    return tuple(
        sorted(paths)
    )


def _git_head_file_bytes(
    relative_path: str,
) -> bytes:
    raw = _run_git(
        "show",
        f"HEAD:{relative_path}",
        binary=True,
    )

    if not isinstance(
        raw,
        bytes,
    ):
        raise RuntimeError(
            "Unexpected text Git blob output."
        )

    return raw


def _sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def _write_exact_bytes(
    *,
    release_root: Path,
    relative_path: str,
    payload: bytes,
) -> None:
    target = (
        release_root
        / Path(relative_path)
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_bytes(
        payload
    )


def _validate_locked_payload(
    payload_paths: tuple[str, ...],
) -> None:
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

    for path in payload_paths:

        normalized = path.replace(
            "\\",
            "/",
        )

        for fragment in forbidden_fragments:
            if fragment in normalized:
                raise RuntimeError(
                    "Forbidden runtime release path: "
                    + normalized
                )

    required_paths = {
        PRODUCTION_REQUIREMENTS_PATH,
        *BACKEND_STATIC_ASSETS,
        *RUNTIME_SCRIPT_FILES,
        *MQL5_RUNTIME_FILES,
    }

    missing = sorted(
        required_paths
        - set(payload_paths)
    )

    if missing:
        raise RuntimeError(
            "Required runtime release paths missing: "
            + ", ".join(missing)
        )


def _build_manifest_entries(
    *,
    release_root: Path,
    payload_paths: tuple[str, ...],
) -> list[dict[str, object]]:
    manifest_paths = sorted(
        (
            *payload_paths,
            GENERATED_VERSION_PATH,
        )
    )

    entries: list[
        dict[str, object]
    ] = []

    for relative_path in manifest_paths:
        path = (
            release_root
            / relative_path
        )

        if not path.is_file():
            raise RuntimeError(
                "Release payload file missing: "
                + relative_path
            )

        payload = path.read_bytes()

        entries.append(
            {
                "path": relative_path,
                "sha256": _sha256_bytes(
                    payload
                ),
                "size": len(payload),
            }
        )

    return entries


def _build_release(
    *,
    output_root: Path,
) -> Path:
    if not output_root.is_absolute():
        raise RuntimeError(
            "--output-root must be an absolute path."
        )

    release_id = (
        _head_release_id()
    )

    final_release_root = (
        output_root
        / release_id
    )

    if final_release_root.exists():
        raise RuntimeError(
            "Release directory already exists: "
            + str(final_release_root)
        )

    payload_paths = (
        _payload_paths()
    )

    _validate_locked_payload(
        payload_paths
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_release_root = (
        output_root
        / (
            ".building-"
            + release_id
            + "-"
            + uuid.uuid4().hex
        )
    )

    if temporary_release_root.exists():
        raise RuntimeError(
            "Temporary release directory "
            "unexpectedly exists."
        )

    temporary_release_root.mkdir(
        parents=False,
        exist_ok=False,
    )

    try:
        for relative_path in payload_paths:
            payload = (
                _git_head_file_bytes(
                    relative_path
                )
            )

            _write_exact_bytes(
                release_root=(
                    temporary_release_root
                ),
                relative_path=(
                    relative_path
                ),
                payload=payload,
            )

        version_payload = (
            release_id
            + "\n"
        ).encode(
            "utf-8"
        )

        _write_exact_bytes(
            release_root=(
                temporary_release_root
            ),
            relative_path=(
                GENERATED_VERSION_PATH
            ),
            payload=version_payload,
        )

        entries = (
            _build_manifest_entries(
                release_root=(
                    temporary_release_root
                ),
                payload_paths=(
                    payload_paths
                ),
            )
        )

        manifest = {
            "schema_version": (
                MANIFEST_SCHEMA_VERSION
            ),
            "release_id": (
                release_id
            ),
            "files": entries,
        }

        manifest_payload = (
            json.dumps(
                manifest,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n"
        ).encode(
            "utf-8"
        )

        _write_exact_bytes(
            release_root=(
                temporary_release_root
            ),
            relative_path=(
                GENERATED_MANIFEST_PATH
            ),
            payload=manifest_payload,
        )

        sha256_payload = (
            "".join(
                (
                    str(entry["sha256"])
                    + "  "
                    + str(entry["path"])
                    + "\n"
                )
                for entry in entries
            )
        ).encode(
            "utf-8"
        )

        _write_exact_bytes(
            release_root=(
                temporary_release_root
            ),
            relative_path=(
                GENERATED_SHA256_PATH
            ),
            payload=sha256_payload,
        )

        # Last pre-publication integrity check.
        actual_files = {
            path.relative_to(
                temporary_release_root
            ).as_posix()
            for path
            in temporary_release_root.rglob("*")
            if path.is_file()
        }

        expected_files = (
            set(payload_paths)
            | {
                GENERATED_VERSION_PATH,
                GENERATED_MANIFEST_PATH,
                GENERATED_SHA256_PATH,
            }
        )

        if actual_files != expected_files:
            raise RuntimeError(
                "Release file boundary mismatch."
            )

        # Publish only after the entire release has been
        # constructed and validated.
        os.replace(
            temporary_release_root,
            final_release_root,
        )

    except BaseException:
        if temporary_release_root.exists():
            shutil.rmtree(
                temporary_release_root,
                ignore_errors=True,
            )
        raise

    return final_release_root


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build one immutable TODOBA production "
            "runtime release from committed Git HEAD."
        )
    )

    parser.add_argument(
        "--output-root",
        required=True,
        type=Path,
        help=(
            "Absolute directory that owns versioned "
            "runtime release directories."
        ),
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> int:
    parser = _build_parser()

    arguments = parser.parse_args(
        argv
    )

    try:
        release_root = _build_release(
            output_root=(
                arguments.output_root
            ),
        )

    except (
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            "TODOBA runtime release build refused: "
            + str(exc),
            file=sys.stderr,
        )
        return 1

    print(
        "RELEASE_BUILD=GREEN"
    )

    print(
        "RELEASE_ROOT="
        + str(release_root)
    )

    print(
        "RELEASE_ID="
        + release_root.name
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
