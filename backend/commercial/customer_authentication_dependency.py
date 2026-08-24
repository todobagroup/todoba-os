"""
TODOBA Customer HTTP Authentication Dependency

Owns the HTTP transport boundary for commercial customer
authentication.

Trust boundary:

    Authorization: Bearer <customer access credential>
        -> extract bearer credential
        -> CustomerAuthenticator
        -> authoritative CustomerIdentity

Authentication failures converge on HTTP 401 with:

    detail:
        Customer authentication failed.

    WWW-Authenticate:
        Bearer

This component does not:
- issue or revoke customer credentials
- persist credentials
- accept customer_id from the caller
- accept deployment_id or agent_id
- accept credentials from query parameters or request bodies
- authorize deployment ownership
- authorize subscription or entitlement
- deliver customer deployment packages
"""

from collections.abc import Callable

from fastapi import Header
from fastapi import HTTPException
from fastapi import status

from backend.commercial.customer_authenticator import (
    CustomerAuthenticator,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)


_BEARER_PREFIX = "Bearer "


def create_customer_authentication_dependency(
    authenticator: CustomerAuthenticator,
) -> Callable[..., CustomerIdentity]:
    """
    Build the FastAPI customer authentication dependency.

    The only credential transport owned here is the
    Authorization header using the Bearer scheme.
    """

    if not isinstance(
        authenticator,
        CustomerAuthenticator,
    ):
        raise TypeError(
            "create_customer_authentication_dependency "
            "requires CustomerAuthenticator."
        )

    def require_customer(
        authorization: str | None = Header(
            default=None,
            alias="Authorization",
        ),
    ) -> CustomerIdentity:
        if not isinstance(
            authorization,
            str,
        ):
            _raise_authentication_failed()

        normalized_authorization = (
            authorization.strip()
        )

        if not normalized_authorization.startswith(
            _BEARER_PREFIX
        ):
            _raise_authentication_failed()

        access_credential = (
            normalized_authorization[
                len(_BEARER_PREFIX):
            ].strip()
        )

        if not access_credential:
            _raise_authentication_failed()

        identity = authenticator.authenticate(
            access_credential
        )

        if identity is None:
            _raise_authentication_failed()

        return identity

    return require_customer


def _raise_authentication_failed() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Customer authentication failed.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )
