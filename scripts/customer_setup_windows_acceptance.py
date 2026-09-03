"""
TODOBA Trading AI Setup frozen acceptance process boundary.

This module is acceptance tooling only.

It may launch the already-built production Windows executable
against a controlled localhost HTTP server.

Security contract:
- accepts only loopback IPv4 HTTP URLs
- accepts no authorization code or customer credential
- passes no customer authority on the command line
- changes only the child-process environment
- never mutates the parent process environment
- never launches through a shell
- never owns server-side customer or deployment authority
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from scripts.build_customer_setup_windows import (
    _packaged_executable_path,
)


_CLOUD_BASE_URL_ENV_NAME = (
    "TODOBA_CLOUD_BASE_URL"
)

_LOOPBACK_HOST = "127.0.0.1"


def normalize_acceptance_base_url(
    value: str,
) -> str:
    """
    Require one plain loopback HTTP origin.
    """

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "acceptance base URL must be str."
        )

    normalized = value.strip().rstrip(
        "/"
    )

    if not normalized:
        raise ValueError(
            "acceptance base URL is required."
        )

    parsed = urlsplit(
        normalized
    )

    if parsed.scheme != "http":
        raise ValueError(
            "acceptance base URL must use HTTP."
        )

    if parsed.hostname != _LOOPBACK_HOST:
        raise ValueError(
            "acceptance base URL must use "
            "127.0.0.1."
        )

    if parsed.username is not None:
        raise ValueError(
            "acceptance base URL must not "
            "contain user information."
        )

    if parsed.password is not None:
        raise ValueError(
            "acceptance base URL must not "
            "contain user information."
        )

    if parsed.query:
        raise ValueError(
            "acceptance base URL must not "
            "contain a query."
        )

    if parsed.fragment:
        raise ValueError(
            "acceptance base URL must not "
            "contain a fragment."
        )

    if parsed.path not in (
        "",
        "/",
    ):
        raise ValueError(
            "acceptance base URL must be "
            "an origin without a path."
        )

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(
            "acceptance base URL has invalid port."
        ) from exc

    if port is None:
        raise ValueError(
            "acceptance base URL requires "
            "an explicit port."
        )

    if not (
        1
        <= port
        <= 65535
    ):
        raise ValueError(
            "acceptance base URL port "
            "is out of range."
        )

    expected_netloc = (
        f"{_LOOPBACK_HOST}:{port}"
    )

    if parsed.netloc != expected_netloc:
        raise ValueError(
            "acceptance base URL is not "
            "a canonical loopback origin."
        )

    return (
        f"http://{expected_netloc}"
    )


def build_acceptance_environment(
    *,
    setup_base_url: str,
    parent_environment: dict[
        str,
        str,
    ] | None = None,
) -> dict[
    str,
    str,
]:
    """
    Return an isolated child-process environment.
    """

    normalized_url = (
        normalize_acceptance_base_url(
            setup_base_url
        )
    )

    if parent_environment is None:
        source_environment = os.environ
    else:
        if not isinstance(
            parent_environment,
            dict,
        ):
            raise TypeError(
                "parent_environment must be dict."
            )

        source_environment = (
            parent_environment
        )

    child_environment = dict(
        source_environment
    )

    child_environment[
        _CLOUD_BASE_URL_ENV_NAME
    ] = normalized_url

    return child_environment


def require_production_executable(
    executable_path: Path | None = None,
) -> Path:
    """
    Resolve and validate the frozen production executable.
    """

    if executable_path is None:
        candidate = (
            _packaged_executable_path()
        )
    else:
        if not isinstance(
            executable_path,
            Path,
        ):
            raise TypeError(
                "executable_path must be Path."
            )

        candidate = executable_path

    resolved = candidate.resolve()

    if not resolved.is_file():
        raise RuntimeError(
            "TODOBA Trading AI Setup.exe "
            "is not available."
        )

    if (
        resolved.name
        != "TODOBA Trading AI Setup.exe"
    ):
        raise RuntimeError(
            "Production Setup executable "
            "name is invalid."
        )

    return resolved


def launch_frozen_customer_setup(
    *,
    setup_base_url: str,
    executable_path: Path | None = None,
    parent_environment: dict[
        str,
        str,
    ] | None = None,
) -> subprocess.Popen:
    """
    Launch the frozen production Setup GUI.

    No credential or customer authority is accepted here.
    """

    executable = (
        require_production_executable(
            executable_path
        )
    )

    child_environment = (
        build_acceptance_environment(
            setup_base_url=(
                setup_base_url
            ),
            parent_environment=(
                parent_environment
            ),
        )
    )

    return subprocess.Popen(
        [
            str(
                executable
            ),
        ],
        cwd=executable.parent,
        env=child_environment,
        shell=False,
    )
