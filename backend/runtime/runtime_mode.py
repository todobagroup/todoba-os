"""
TODOBA Runtime Mode

Owns runtime composition selection.

Responsibilities:

- Define supported runtime modes
- Build Cloud Control Plane runtime
- Build Local Trading runtime

Cloud mode must not load local MT5 Trading infrastructure.
"""

from __future__ import annotations

from enum import Enum

from backend.runtime.todoba_runtime import (
    TODOBARuntime,
)


class RuntimeMode(str, Enum):
    CLOUD = "CLOUD"
    LOCAL_TRADING = "LOCAL_TRADING"


def create_runtime(
    mode: RuntimeMode,
) -> TODOBARuntime:
    """
    Create TODOBA runtime for the requested mode.
    """

    if not isinstance(
        mode,
        RuntimeMode,
    ):
        raise TypeError(
            "create_runtime requires RuntimeMode."
        )

    if mode is RuntimeMode.CLOUD:
        return TODOBARuntime()

    if mode is RuntimeMode.LOCAL_TRADING:
        from backend.runtime.runtime_bootstrap import (
            RuntimeBootstrap,
        )

        return RuntimeBootstrap().create_runtime()

    raise ValueError(
        f"Unsupported runtime mode: {mode}"
    )