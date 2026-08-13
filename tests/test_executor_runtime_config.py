"""
TODOBA Executor Runtime Configuration Tests

Proof:

TODOBA_EXECUTOR_ID
TODOBA_EXECUTOR_SECRET
->
backend.config
->
Executor authentication configuration
"""

import importlib
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


def reload_config(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "TODOBA_EXECUTOR_ID",
        "telegram-executor-proof091",
    )

    monkeypatch.setenv(
        "TODOBA_EXECUTOR_SECRET",
        "proof091-executor-secret",
    )

    import backend.config as config

    return importlib.reload(
        config
    )


def test_executor_runtime_config_loads_executor_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = reload_config(
        monkeypatch
    )

    assert loaded.TODOBA_EXECUTOR_ID == (
        "telegram-executor-proof091"
    )


def test_executor_runtime_config_loads_executor_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = reload_config(
        monkeypatch
    )

    assert loaded.TODOBA_EXECUTOR_SECRET == (
        "proof091-executor-secret"
    )