"""
TODOBA Trusted Agent Authenticator

Owns authentication of Trusted Agents across the
remote HTTP execution boundary.

Mission contracts, authorization, signing, replay
protection, and broker execution belong to separate
capabilities.
"""

from hmac import compare_digest


class TrustedAgentAuthenticator:
    """
    Authenticate one Trusted Agent identity using
    a shared secret supplied through HTTP headers.
    """

    def __init__(
        self,
        agent_id: str,
        agent_secret: str,
    ) -> None:
        normalized_agent_id = agent_id.strip()
        normalized_agent_secret = agent_secret.strip()

        if not normalized_agent_id:
            raise ValueError(
                "agent_id is required."
            )

        if not normalized_agent_secret:
            raise ValueError(
                "agent_secret is required."
            )

        self._agent_id = normalized_agent_id
        self._agent_secret = normalized_agent_secret

    def authenticate(
        self,
        agent_id: str | None,
        authorization: str | None,
    ) -> bool:
        if agent_id is None:
            return False

        if authorization is None:
            return False

        supplied_agent_id = agent_id.strip()
        supplied_authorization = authorization.strip()

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

        agent_matches = compare_digest(
            supplied_agent_id,
            self._agent_id,
        )

        secret_matches = compare_digest(
            supplied_secret,
            self._agent_secret,
        )

        return agent_matches and secret_matches