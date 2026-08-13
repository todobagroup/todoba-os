"""
TODOBA Main Executor Authentication Composition Tests

Proof:

backend.main
->
ExecutorAuthenticator
->
authenticated /missions/inject
"""

import importlib
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


def test_main_composes_executor_authenticator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TODOBA_EXECUTOR_ID",
        "telegram-executor-proof091",
    )

    monkeypatch.setenv(
        "TODOBA_EXECUTOR_SECRET",
        "proof091-executor-secret",
    )

    import backend.config as config

    importlib.reload(
        config
    )

    sys.modules.pop(
        "backend.main",
        None,
    )

    main = importlib.import_module(
        "backend.main"
    )

    from backend.trading.execution.executor_authenticator import (
        ExecutorAuthenticator,
    )

    assert isinstance(
        main.executor_authenticator,
        ExecutorAuthenticator,
    )

    assert main.executor_authenticator.authenticate(
        executor_id="telegram-executor-proof091",
        authorization=(
            "Bearer proof091-executor-secret"
        ),
    )