"""
TODOBA Trusted Agent Authenticator

Owns authentication of Trusted Agents across the
remote HTTP execution boundary.

Mission contracts, authorization, signing, replay
protection, and broker execution belong to separate
capabilities.
"""

from hmac import compare_digest

from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
)


class TrustedAgentAuthenticator:
    """
    Authenticate Trusted Agent identities using
    Agent-specific shared secrets.

    The legacy single-Agent constructor remains supported
    for backward-compatible deployment composition.
    """

    def __init__(
        self,
        agent_id: str | None = None,
        agent_secret: str | None = None,
        *,
        credential_registry: (
            TrustedAgentCredentialRegistry | None
        ) = None,
    ) -> None:
        if credential_registry is not None:
            if not isinstance(
                credential_registry,
                TrustedAgentCredentialRegistry,
            ):
                raise TypeError(
                    "credential_registry must be "
                    "TrustedAgentCredentialRegistry."
                )

            if (
                agent_id is not None
                or agent_secret is not None
            ):
                raise ValueError(
                    "Provide either legacy Agent "
                    "credentials or credential_registry, "
                    "not both."
                )

            self._credential_registry = (
                credential_registry
            )

            return

        if not isinstance(
            agent_id,
            str,
        ):
            raise ValueError(
                "agent_id is required."
            )

        if not isinstance(
            agent_secret,
            str,
        ):
            raise ValueError(
                "agent_secret is required."
            )

        normalized_agent_id = agent_id.strip()
        normalized_agent_secret = (
            agent_secret.strip()
        )

        if not normalized_agent_id:
            raise ValueError(
                "agent_id is required."
            )

        if not normalized_agent_secret:
            raise ValueError(
                "agent_secret is required."
            )

        legacy_registry = (
            TrustedAgentCredentialRegistry()
        )

        legacy_registry.register(
            agent_id=normalized_agent_id,
            agent_secret=normalized_agent_secret,
        )

        self._credential_registry = (
            legacy_registry
        )

    def authenticate(
        self,
        agent_id: str | None,
        authorization: str | None,
    ) -> bool:
        if not isinstance(
            agent_id,
            str,
        ):
            return False

        if not isinstance(
            authorization,
            str,
        ):
            return False

        supplied_agent_id = agent_id.strip()
        supplied_authorization = (
            authorization.strip()
        )

        if not supplied_agent_id:
            return False

        bearer_prefix = "Bearer "

        if not supplied_authorization.startswith(
            bearer_prefix
        ):
            return False

        supplied_secret = supplied_authorization[
            len(bearer_prefix):
        ].strip()

        if not supplied_secret:
            return False

        expected_secret = (
            self._credential_registry.get_secret(
                agent_id=supplied_agent_id
            )
        )

        if expected_secret is None:
            return False

        return compare_digest(
            supplied_secret,
            expected_secret,
        )