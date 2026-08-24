"""
TODOBA Customer Authenticator

Authenticates one commercial customer from an opaque
Customer Access Credential.

Trust boundary:

    access credential
        -> parse credential structure
        -> credential_id lookup
        -> derive supplied verifier
        -> constant-time verifier comparison
        -> ACTIVE credential required
        -> authoritative CustomerIdentity

Authentication never accepts customer_id, deployment_id,
agent_id, entitlement, or package identifiers from the
caller as proof of customer identity.

All invalid authentication attempts converge on None.

This component does not:
- issue or revoke credentials
- persist credential secrets
- parse HTTP Authorization headers
- create sessions
- own customer identity
- authorize deployment ownership
- authorize entitlement
- deliver deployment packages
"""

from hmac import compare_digest

from backend.commercial.customer_access_credential_registry import (
    CUSTOMER_ACCESS_CREDENTIAL_PREFIX,
    CustomerAccessCredentialRegistry,
    CustomerAccessCredentialStatus,
    derive_customer_access_credential_verifier,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)


class CustomerAuthenticator:
    """
    Authenticate opaque customer access credentials.

    Success returns the authoritative CustomerIdentity.

    Any invalid, malformed, unknown, mismatched, or revoked
    credential returns None.
    """

    def __init__(
        self,
        *,
        credential_registry: (
            CustomerAccessCredentialRegistry
        ),
    ) -> None:
        if not isinstance(
            credential_registry,
            CustomerAccessCredentialRegistry,
        ):
            raise TypeError(
                "credential_registry must be "
                "CustomerAccessCredentialRegistry."
            )

        if not credential_registry.is_ready():
            raise RuntimeError(
                "Customer access credential registry "
                "is not initialized."
            )

        self._credential_registry = (
            credential_registry
        )

    def authenticate(
        self,
        access_credential: str | None,
    ) -> CustomerIdentity | None:
        """
        Authenticate one supplied customer credential.

        Fail-closed cases include:
        - missing credential
        - empty credential
        - malformed structure
        - wrong credential prefix
        - malformed credential_id
        - unknown credential_id
        - incorrect secret
        - revoked credential
        - missing authoritative customer identity
        """

        parsed = self._parse_access_credential(
            access_credential
        )

        if parsed is None:
            return None

        (
            normalized_access_credential,
            credential_id,
        ) = parsed

        try:
            record = (
                self._credential_registry.get(
                    credential_id=credential_id
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if record is None:
            return None

        try:
            supplied_verifier = (
                derive_customer_access_credential_verifier(
                    normalized_access_credential
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        verifier_matches = compare_digest(
            supplied_verifier,
            record.verifier_sha256,
        )

        if not verifier_matches:
            return None

        if (
            record.status
            is not CustomerAccessCredentialStatus.ACTIVE
        ):
            return None

        identity = (
            self._credential_registry
            .customer_identity_registry
            .get(
                customer_id=record.customer_id
            )
        )

        if identity is None:
            return None

        return identity

    @staticmethod
    def _parse_access_credential(
        access_credential: str | None,
    ) -> tuple[
        str,
        str,
    ] | None:
        if not isinstance(
            access_credential,
            str,
        ):
            return None

        normalized = access_credential.strip()

        if not normalized:
            return None

        parts = normalized.split(
            "."
        )

        if len(parts) != 3:
            return None

        (
            prefix,
            credential_id,
            secret,
        ) = parts

        if (
            prefix
            != CUSTOMER_ACCESS_CREDENTIAL_PREFIX
        ):
            return None

        if not credential_id:
            return None

        if not secret:
            return None

        return (
            normalized,
            credential_id,
        )
