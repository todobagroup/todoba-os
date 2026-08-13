"""
TODOBA Executor Authentication Dependency Tests

Proof:

Executor HTTP headers
->
ExecutorAuthenticator
->
FastAPI dependency
->
valid credentials accepted
invalid credentials rejected with 401
"""

import sys
from pathlib import Path

from fastapi import Depends
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.trading.execution.executor_authentication_dependency import (
    create_executor_authentication_dependency,
)
from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)


def create_test_client() -> TestClient:
    authenticator = ExecutorAuthenticator(
        executor_id="telegram-executor-001",
        executor_secret="proof091-secret",
    )

    require_executor = (
        create_executor_authentication_dependency(
            authenticator
        )
    )

    app = FastAPI()

    @app.get("/protected")
    def protected(
        executor_id: str = Depends(
            require_executor
        ),
    ):
        return {
            "executor_id": executor_id,
        }

    return TestClient(app)


def test_valid_executor_credentials_are_accepted():
    client = create_test_client()

    response = client.get(
        "/protected",
        headers={
            "X-TODOBA-Executor-ID": (
                "telegram-executor-001"
            ),
            "Authorization": (
                "Bearer proof091-secret"
            ),
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "executor_id": "telegram-executor-001",
    }


def test_invalid_executor_secret_returns_401():
    client = create_test_client()

    response = client.get(
        "/protected",
        headers={
            "X-TODOBA-Executor-ID": (
                "telegram-executor-001"
            ),
            "Authorization": (
                "Bearer wrong-secret"
            ),
        },
    )

    assert response.status_code == 401


def test_missing_executor_headers_return_401():
    client = create_test_client()

    response = client.get(
        "/protected"
    )

    assert response.status_code == 401