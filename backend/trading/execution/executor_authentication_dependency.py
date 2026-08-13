"""
TODOBA Executor Authentication Dependency

Adapts ExecutorAuthenticator to the FastAPI HTTP
boundary.

Authentication policy belongs to
ExecutorAuthenticator. This module owns HTTP header
extraction, unauthorized responses, and authenticated
Executor identity delivery only.
"""

from collections.abc import Callable

from fastapi import Header
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)


def create_executor_authentication_dependency(
    authenticator: ExecutorAuthenticator,
) -> Callable[..., str]:
    if not isinstance(
        authenticator,
        ExecutorAuthenticator,
    ):
        raise TypeError(
            "create_executor_authentication_dependency "
            "requires ExecutorAuthenticator."
        )

    def require_executor(
        executor_id: str | None = Header(
            default=None,
            alias="X-TODOBA-Executor-ID",
        ),
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> str:
        if not authenticator.authenticate(
            executor_id=executor_id,
            authorization=authorization,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Executor authentication failed.",
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )

        return executor_id.strip()

    return require_executor