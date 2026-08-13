"""
TODOBA Telegram Remote VPS Execution Mode Tests

Proof:

REMOTE_VPS mode
->
does not construct local RuntimeBootstrap
->
does not require local MetaTrader5 runtime
"""

import builtins
import importlib
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


def test_remote_vps_mode_does_not_load_local_runtime_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TELEGRAM_EXECUTION_MODE",
        "REMOTE_VPS",
    )

    import backend.config as config

    importlib.reload(
        config
    )

    sys.modules.pop(
        "backend.integrations.telegram_listener",
        None,
    )

    original_import = builtins.__import__

    def guarded_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name == (
            "backend.runtime.runtime_bootstrap"
        ):
            raise AssertionError(
                "REMOTE_VPS mode must not load "
                "RuntimeBootstrap."
            )

        if name == "MetaTrader5":
            raise AssertionError(
                "REMOTE_VPS mode must not load "
                "MetaTrader5."
            )

        return original_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        builtins,
        "__import__",
        guarded_import,
    )

    importlib.import_module(
        "backend.integrations.telegram_listener"
    )