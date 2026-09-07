"""
TODOBA Production Package Builder Runtime.

Dedicated supervised runtime owner for automatic processing
of durable customer deployment package-build requests.

Security / ownership boundaries:
- does not import or start backend.main
- does not expose HTTP
- does not create customer setup authority
- does not initialize missing durable state
- uses the existing recovery-only package-build runner
- machine-local MetaTrader build paths come from environment
- queue/build failures fail closed and let the Windows
  runtime supervisor restart this process
"""

from __future__ import annotations

import os
from pathlib import Path
import time

from scripts import (
    process_customer_deployment_package_build_requests
    as package_build_runner,
)


_PLATFORM_MQL5_ROOT_ENV = (
    "TODOBA_PACKAGE_BUILDER_PLATFORM_MQL5_ROOT"
)

_METAEDITOR_PATH_ENV = (
    "TODOBA_PACKAGE_BUILDER_METAEDITOR_PATH"
)

_WORKSPACE_ROOT_ENV = (
    "TODOBA_PACKAGE_BUILDER_WORKSPACE_ROOT"
)

_POLL_INTERVAL_ENV = (
    "TODOBA_PACKAGE_BUILDER_POLL_SECONDS"
)

_DEFAULT_POLL_INTERVAL_SECONDS = 2.0

_MINIMUM_POLL_INTERVAL_SECONDS = 0.5

_MAXIMUM_POLL_INTERVAL_SECONDS = 60.0


def _require_machine_path(
    *,
    environment_name: str,
    kind: str,
) -> Path:
    raw_value = os.getenv(
        environment_name,
        "",
    ).strip()

    if not raw_value:
        raise RuntimeError(
            f"{environment_name} is required."
        )

    path = Path(
        raw_value
    )

    if not path.is_absolute():
        raise RuntimeError(
            f"{environment_name} must be an absolute path."
        )

    resolved = path.resolve()

    if kind == "file":
        if not resolved.is_file():
            raise RuntimeError(
                f"{environment_name} must reference "
                "an existing file."
            )

    elif kind == "directory":
        if not resolved.is_dir():
            raise RuntimeError(
                f"{environment_name} must reference "
                "an existing directory."
            )

    else:
        raise RuntimeError(
            "Unsupported package-builder path kind."
        )

    return resolved


def _poll_interval_seconds() -> float:
    raw_value = os.getenv(
        _POLL_INTERVAL_ENV,
        str(
            _DEFAULT_POLL_INTERVAL_SECONDS
        ),
    ).strip()

    try:
        value = float(
            raw_value
        )
    except ValueError as error:
        raise RuntimeError(
            f"{_POLL_INTERVAL_ENV} must be numeric."
        ) from error

    if not (
        _MINIMUM_POLL_INTERVAL_SECONDS
        <= value
        <= _MAXIMUM_POLL_INTERVAL_SECONDS
    ):
        raise RuntimeError(
            f"{_POLL_INTERVAL_ENV} must be between "
            f"{_MINIMUM_POLL_INTERVAL_SECONDS} and "
            f"{_MAXIMUM_POLL_INTERVAL_SECONDS}."
        )

    return value


def _process_queue_once(
    *,
    platform_mql5_root: Path,
    metaeditor_path: Path,
    workspace_root: Path,
):
    """
    Recompose recovery-only owners for every poll.

    This is deliberate. Customer Setup can persist a new
    deployment, secret, binding, bootstrap and build request
    after this process started. Recomposition ensures each
    poll reads current durable production truth rather than
    retaining a stale in-memory commercial snapshot.
    """

    (
        build_request_store,
        worker,
    ) = (
        package_build_runner
        ._compose_customer_deployment_package_build_runner(
            control_plane_root=(
                package_build_runner
                .TODOBA_CONTROL_PLANE_DATA_ROOT
            ),
            encoded_master_key=(
                package_build_runner
                .TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY
            ),
            mql5_source_root=(
                package_build_runner
                .REPOSITORY_MQL5_SOURCE_ROOT
            ),
            platform_mql5_root=(
                platform_mql5_root
            ),
            workspace_root=(
                workspace_root
            ),
            package_root=(
                package_build_runner
                .get_customer_package_root()
            ),
            metaeditor_path=(
                metaeditor_path
            ),
        )
    )

    return (
        package_build_runner
        .process_customer_deployment_package_build_requests(
            build_request_store=(
                build_request_store
            ),
            worker=worker,
        )
    )


def run_package_builder() -> None:
    platform_mql5_root = (
        _require_machine_path(
            environment_name=(
                _PLATFORM_MQL5_ROOT_ENV
            ),
            kind="directory",
        )
    )

    metaeditor_path = (
        _require_machine_path(
            environment_name=(
                _METAEDITOR_PATH_ENV
            ),
            kind="file",
        )
    )

    workspace_root = (
        _require_machine_path(
            environment_name=(
                _WORKSPACE_ROOT_ENV
            ),
            kind="directory",
        )
    )

    poll_interval_seconds = (
        _poll_interval_seconds()
    )

    print(
        "TODOBA_PACKAGE_BUILDER_RUNTIME=STARTED",
        flush=True,
    )

    while True:
        summary = (
            _process_queue_once(
                platform_mql5_root=(
                    platform_mql5_root
                ),
                metaeditor_path=(
                    metaeditor_path
                ),
                workspace_root=(
                    workspace_root
                ),
            )
        )

        if (
            summary.built > 0
            or summary.busy > 0
        ):
            package_build_runner._print_safe_summary(
                summary
            )

        time.sleep(
            poll_interval_seconds
        )


def main() -> int:
    run_package_builder()

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
