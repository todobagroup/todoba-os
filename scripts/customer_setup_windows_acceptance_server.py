"""
TODOBA customer Setup isolated production server harness.

Acceptance tooling only.

This owner prepares an isolated customer Setup control plane and
starts the real production FastAPI application on one loopback
port.

It does not:
- issue bootstrap authorization
- accept customer identity
- accept customer credentials
- launch the frozen Setup executable
- build customer packages
- mutate production control-plane state

Bootstrap authorization issuance intentionally remains outside
this owner because issuance requires the TODOBA runtime to be
stopped.
"""

from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Mapping

from scripts.provision_customer_setup_control_plane import (
    provision_customer_setup_control_plane,
)


_CONTROL_PLANE_ENV_NAME = (
    "TODOBA_CONTROL_PLANE_DATA_ROOT"
)

_PACKAGE_ROOT_ENV_NAME = (
    "TODOBA_CUSTOMER_PACKAGE_ROOT"
)

_MASTER_KEY_ENV_NAME = (
    "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY"
)

_LOOPBACK_HOST = "127.0.0.1"


def _repository_root() -> Path:
    return (
        Path(__file__)
        .resolve()
        .parents[1]
    )


def validate_loopback_port(
    port: int,
) -> int:
    if (
        not isinstance(
            port,
            int,
        )
        or isinstance(
            port,
            bool,
        )
    ):
        raise TypeError(
            "port must be int."
        )

    if not (
        1
        <= port
        <= 65535
    ):
        raise ValueError(
            "port must be between "
            "1 and 65535."
        )

    return port


def _require_external_directory_path(
    *,
    name: str,
    path: Path,
) -> Path:
    if not isinstance(
        path,
        Path,
    ):
        raise TypeError(
            f"{name} must be Path."
        )

    resolved = path.resolve()

    repository_root = (
        _repository_root()
        .resolve()
    )

    if (
        resolved == repository_root
        or repository_root
        in resolved.parents
    ):
        raise ValueError(
            f"{name} must be outside "
            "the repository."
        )

    return resolved


def validate_encoded_master_key(
    value: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "encoded_master_key must be str."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            "encoded_master_key is required."
        )

    return normalized


def build_server_environment(
    *,
    control_plane_root: Path,
    package_root: Path,
    encoded_master_key: str,
    parent_environment: Mapping[
        str,
        str,
    ] | None = None,
) -> dict[
    str,
    str,
]:
    """
    Build one isolated child-process environment.

    The supplied master key is never printed or placed on the
    command line.
    """

    resolved_control_plane_root = (
        _require_external_directory_path(
            name="control_plane_root",
            path=control_plane_root,
        )
    )

    resolved_package_root = (
        _require_external_directory_path(
            name="package_root",
            path=package_root,
        )
    )

    if (
        resolved_control_plane_root
        == resolved_package_root
    ):
        raise ValueError(
            "control_plane_root and "
            "package_root must be distinct."
        )

    normalized_master_key = (
        validate_encoded_master_key(
            encoded_master_key
        )
    )

    if parent_environment is None:
        source_environment = os.environ
    else:
        if not isinstance(
            parent_environment,
            Mapping,
        ):
            raise TypeError(
                "parent_environment must be Mapping."
            )

        source_environment = (
            parent_environment
        )

    child_environment = dict(
        source_environment
    )

    child_environment[
        _CONTROL_PLANE_ENV_NAME
    ] = str(
        resolved_control_plane_root
    )

    child_environment[
        _PACKAGE_ROOT_ENV_NAME
    ] = str(
        resolved_package_root
    )

    child_environment[
        _MASTER_KEY_ENV_NAME
    ] = normalized_master_key

    return child_environment


def prepare_isolated_control_plane(
    *,
    control_plane_root: Path,
    package_root: Path,
) -> None:
    """
    Provision empty durable Setup stores before runtime starts.
    """

    resolved_control_plane_root = (
        _require_external_directory_path(
            name="control_plane_root",
            path=control_plane_root,
        )
    )

    resolved_package_root = (
        _require_external_directory_path(
            name="package_root",
            path=package_root,
        )
    )

    if (
        resolved_control_plane_root
        == resolved_package_root
    ):
        raise ValueError(
            "control_plane_root and "
            "package_root must be distinct."
        )

    resolved_control_plane_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    resolved_package_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    provision_customer_setup_control_plane(
        control_plane_root=(
            resolved_control_plane_root
        ),
        confirm_runtime_stopped=True,
    )


def start_production_server(
    *,
    port: int,
    environment: Mapping[
        str,
        str,
    ],
) -> subprocess.Popen:
    """
    Start backend.main:app on canonical IPv4 loopback only.
    """

    validated_port = (
        validate_loopback_port(
            port
        )
    )

    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment must be Mapping."
        )

    child_environment = dict(
        environment
    )

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        _LOOPBACK_HOST,
        "--port",
        str(
            validated_port
        ),
        "--log-level",
        "warning",
    ]

    return subprocess.Popen(
        command,
        cwd=_repository_root(),
        env=child_environment,
        shell=False,
    )


def wait_for_server_ready(
    *,
    process: subprocess.Popen,
    port: int,
    timeout_seconds: float = 15.0,
) -> None:
    """
    Require the production server to bind loopback successfully.
    """

    if not isinstance(
        process,
        subprocess.Popen,
    ):
        raise TypeError(
            "process must be subprocess.Popen."
        )

    validated_port = (
        validate_loopback_port(
            port
        )
    )

    if not isinstance(
        timeout_seconds,
        (
            int,
            float,
        ),
    ):
        raise TypeError(
            "timeout_seconds must be numeric."
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be positive."
        )

    deadline = (
        time.monotonic()
        + float(
            timeout_seconds
        )
    )

    while (
        time.monotonic()
        < deadline
    ):
        return_code = process.poll()

        if return_code is not None:
            raise RuntimeError(
                "Production acceptance server "
                "exited before becoming ready."
            )

        try:
            with socket.create_connection(
                (
                    _LOOPBACK_HOST,
                    validated_port,
                ),
                timeout=0.25,
            ):
                return
        except OSError:
            time.sleep(
                0.05
            )

    raise RuntimeError(
        "Production acceptance server "
        "did not become ready."
    )


def stop_production_server(
    *,
    process: subprocess.Popen,
    timeout_seconds: float = 10.0,
) -> None:
    """
    Stop the isolated production server with a bounded fallback.
    """

    if not isinstance(
        process,
        subprocess.Popen,
    ):
        raise TypeError(
            "process must be subprocess.Popen."
        )

    if not isinstance(
        timeout_seconds,
        (
            int,
            float,
        ),
    ):
        raise TypeError(
            "timeout_seconds must be numeric."
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be positive."
        )

    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(
            timeout=float(
                timeout_seconds
            )
        )
    except subprocess.TimeoutExpired:
        process.kill()

        process.wait(
            timeout=float(
                timeout_seconds
            )
        )
