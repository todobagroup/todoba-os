"""
TODOBA Executor Authentication Tests

Proof:

Executor ID + Executor Secret
->
ExecutorAuthenticator
->
valid credentials accepted
invalid credentials rejected
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)


def test_executor_authentication_accepts_valid_credentials():
    authenticator = ExecutorAuthenticator(
        executor_id="telegram-executor-001",
        executor_secret="proof091-secret",
    )

    assert authenticator.authenticate(
        executor_id="telegram-executor-001",
        authorization="Bearer proof091-secret",
    )


def test_executor_authentication_rejects_invalid_secret():
    authenticator = ExecutorAuthenticator(
        executor_id="telegram-executor-001",
        executor_secret="proof091-secret",
    )

    assert not authenticator.authenticate(
        executor_id="telegram-executor-001",
        authorization="Bearer wrong-secret",
    )


def test_executor_authentication_rejects_invalid_executor_id():
    authenticator = ExecutorAuthenticator(
        executor_id="telegram-executor-001",
        executor_secret="proof091-secret",
    )

    assert not authenticator.authenticate(
        executor_id="wrong-executor",
        authorization="Bearer proof091-secret",
    )


def test_executor_authentication_rejects_missing_headers():
    authenticator = ExecutorAuthenticator(
        executor_id="telegram-executor-001",
        executor_secret="proof091-secret",
    )

    assert not authenticator.authenticate(
        executor_id=None,
        authorization=None,
    )