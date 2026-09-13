"""
TODOBA Commercial Operator Authenticator

Owns authentication of privileged commercial operator
identities.

HTTP header extraction, VND bank reconciliation, payment
evidence publication, settlement, activation, and network
access belong to separate capabilities.
"""

from __future__ import annotations

from hmac import compare_digest


class CommercialOperatorAuthenticator:
    """
    Authenticate one configured commercial operator identity
    using an opaque bearer secret.

    A caller-supplied operator_id is never sufficient to
    establish authenticated operator identity.
    """

    def __init__(
        self,
        *,
        operator_id: str,
        operator_secret: str,
    ) -> None:
        if not isinstance(operator_id, str):
            raise ValueError("operator_id is required.")

        if not isinstance(operator_secret, str):
            raise ValueError("operator_secret is required.")

        normalized_operator_id = operator_id.strip()
        normalized_operator_secret = operator_secret.strip()

        if not normalized_operator_id:
            raise ValueError("operator_id is required.")

        if not normalized_operator_secret:
            raise ValueError("operator_secret is required.")

        self._operator_id = normalized_operator_id
        self._operator_secret = normalized_operator_secret

    def authenticate(
        self,
        *,
        operator_id: str | None,
        authorization: str | None,
    ) -> str | None:
        if not isinstance(operator_id, str):
            return None

        if not isinstance(authorization, str):
            return None

        supplied_operator_id = operator_id.strip()
        supplied_authorization = authorization.strip()

        if not supplied_operator_id:
            return None

        bearer_prefix = "Bearer "

        if not supplied_authorization.startswith(
            bearer_prefix
        ):
            return None

        supplied_secret = supplied_authorization[
            len(bearer_prefix):
        ].strip()

        if not supplied_secret:
            return None

        if not compare_digest(
            supplied_operator_id,
            self._operator_id,
        ):
            return None

        if not compare_digest(
            supplied_secret,
            self._operator_secret,
        ):
            return None

        return self._operator_id
