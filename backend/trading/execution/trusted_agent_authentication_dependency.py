"""
TODOBA Trusted Agent Authentication Dependency

Adapts TrustedAgentAuthenticator to the FastAPI HTTP
boundary.

Authentication policy belongs to
TrustedAgentAuthenticator. This module owns HTTP header
extraction, unauthorized responses, and authenticated
Agent identity delivery only.
"""

from collections.abc import Callable

from fastapi import Header
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def create_trusted_agent_authentication_dependency(
    authenticator: TrustedAgentAuthenticator,
) -> Callable[..., str]:
    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_trusted_agent_authentication_dependency "
            "requires TrustedAgentAuthenticator."
        )

    def require_trusted_agent(
        agent_id: str | None = Header(
            default=None,
            alias="X-TODOBA-Agent-ID",
        ),
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> str:
        if not authenticator.authenticate(
            agent_id=agent_id,
            authorization=authorization,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Trusted Agent authentication failed.",
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )

        return agent_id.strip()

    return require_trusted_agent