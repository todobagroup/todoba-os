"""
TODOBA Trusted Agent Signing Key Registry

Owns Agent-specific mission signing secrets.

Responsibilities:
- register per-Agent signing secrets
- provide Agent-specific signing key lookup
- accept identical registration idempotently
- reject conflicting signing key replacement

Separate registry instances represent separate
signing security domains.

This component does not:
- authenticate Trusted Agents
- sign missions
- persist secrets
- own account bindings
"""

class TrustedAgentSigningKeyRegistry:
    """
    Registry of Trusted Agent signing secrets.

    Identity:
        agent_id

    Authoritative value:
        signing_secret
    """

    def __init__(
        self,
    ) -> None:
        self._signing_keys: dict[
            str,
            str,
        ] = {}

    def register(
        self,
        *,
        agent_id: str,
        signing_secret: str,
    ) -> str:
        normalized_agent_id = (
            self._normalize_agent_id(
                agent_id
            )
        )

        normalized_signing_secret = (
            self._normalize_signing_secret(
                signing_secret
            )
        )

        existing = self._signing_keys.get(
            normalized_agent_id
        )

        if existing is not None:
            if (
                existing
                != normalized_signing_secret
            ):
                raise ValueError(
                    "Trusted Agent signing key is "
                    "already registered with a "
                    "different secret."
                )

            return existing

        self._signing_keys[
            normalized_agent_id
        ] = normalized_signing_secret

        return normalized_signing_secret

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

        return self._signing_keys.get(
            normalized_agent_id
        )

    def size(
        self,
    ) -> int:
        return len(
            self._signing_keys
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
    def _normalize_signing_secret(
        signing_secret: str,
    ) -> str:
        if not isinstance(
            signing_secret,
            str,
        ):
            raise TypeError(
                "signing_secret must be str."
            )

        if signing_secret == "":
            raise ValueError(
                "signing_secret is required."
            )

        return signing_secret