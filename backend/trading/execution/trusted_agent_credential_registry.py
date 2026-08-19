"""
TODOBA Trusted Agent Credential Registry

Owns the in-memory credential registry for Trusted Agents.

Responsibilities:
- register Trusted Agent credentials
- provide Agent-specific credential lookup
- accept identical registration idempotently
- reject conflicting credential replacement

This component does not:
- authenticate HTTP requests
- own account bindings
- persist credentials
- sign missions
"""

class TrustedAgentCredentialRegistry:
    """
    Registry of Trusted Agent credentials.

    Identity:
        agent_id

    Authoritative value:
        agent_secret
    """

    def __init__(
        self,
    ) -> None:
        self._credentials: dict[
            str,
            str,
        ] = {}

    def register(
        self,
        *,
        agent_id: str,
        agent_secret: str,
    ) -> str:
        normalized_agent_id = (
            self._normalize_agent_id(
                agent_id
            )
        )

        normalized_agent_secret = (
            self._normalize_agent_secret(
                agent_secret
            )
        )

        existing = self._credentials.get(
            normalized_agent_id
        )

        if existing is not None:
            if (
                existing
                != normalized_agent_secret
            ):
                raise ValueError(
                    "Trusted Agent credential is "
                    "already registered with a "
                    "different secret."
                )

            return existing

        self._credentials[
            normalized_agent_id
        ] = normalized_agent_secret

        return normalized_agent_secret

    def get_secret(
        self,
        *,
        agent_id: str,
    ) -> str | None:
        normalized_agent_id = (
            self._normalize_agent_id(
                agent_id
            )
        )

        return self._credentials.get(
            normalized_agent_id
        )

    def size(
        self,
    ) -> int:
        return len(
            self._credentials
        )

    @staticmethod
    def _normalize_agent_id(
        agent_id: str,
    ) -> str:
        if not isinstance(
            agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be str."
            )

        normalized = agent_id.strip()

        if not normalized:
            raise ValueError(
                "agent_id is required."
            )

        return normalized

    @staticmethod
    def _normalize_agent_secret(
        agent_secret: str,
    ) -> str:
        if not isinstance(
            agent_secret,
            str,
        ):
            raise TypeError(
                "agent_secret must be str."
            )

        normalized = agent_secret.strip()

        if not normalized:
            raise ValueError(
                "agent_secret is required."
            )

        return normalized