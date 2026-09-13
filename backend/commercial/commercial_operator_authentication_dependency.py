"""
TODOBA Commercial Operator Authentication Dependency

Adapts CommercialOperatorAuthenticator to the FastAPI HTTP
boundary.

Authentication policy belongs to
CommercialOperatorAuthenticator. This module owns HTTP header
extraction, unauthorized responses, and authenticated operator
identity delivery only.
"""

from collections.abc import Callable

from fastapi import Header
from fastapi import HTTPException
from fastapi import status

from backend.commercial.commercial_operator_authenticator import (
    CommercialOperatorAuthenticator,
)


def create_commercial_operator_authentication_dependency(
    authenticator: CommercialOperatorAuthenticator,
) -> Callable[..., str]:
    if not isinstance(
        authenticator,
        CommercialOperatorAuthenticator,
    ):
        raise TypeError(
            "create_commercial_operator_authentication_dependency "
            "requires CommercialOperatorAuthenticator."
        )

    def require_commercial_operator(
        operator_id: str | None = Header(
            default=None,
            alias="X-TODOBA-Operator-ID",
        ),
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> str:
        authenticated_operator_id = authenticator.authenticate(
            operator_id=operator_id,
            authorization=authorization,
        )

        if authenticated_operator_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Commercial operator authentication failed.",
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )

        return authenticated_operator_id

    return require_commercial_operator
