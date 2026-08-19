"""
TODOBA Execution Mission Signer

Creates and verifies integrity signatures for
ExecutionMission payloads.

Responsibilities:

- create HMAC-SHA256 signatures
- verify mission signatures
- use the cross-language signing payload contract
- resolve Agent-specific signing secrets

This component does not:

- authenticate Trusted Agents
- provide replay protection
- receive HTTP requests
- execute broker orders
"""

import hashlib
import hmac

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_signing_payload import (
    ExecutionMissionSigningPayload,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)


class ExecutionMissionSigner:
    """
    Sign and verify ExecutionMission payload integrity.

    Legacy single-secret construction remains supported.
    Multi-Agent construction resolves the signing secret
    from the mission Agent identity.
    """

    def __init__(
        self,
        signing_secret: str | None = None,
        *,
        signing_key_registry: (
            TrustedAgentSigningKeyRegistry | None
        ) = None,
    ) -> None:
        if (
            signing_secret is not None
            and signing_key_registry is not None
        ):
            raise ValueError(
                "Provide either signing_secret or "
                "signing_key_registry, not both."
            )

        if signing_key_registry is not None:
            if not isinstance(
                signing_key_registry,
                TrustedAgentSigningKeyRegistry,
            ):
                raise TypeError(
                    "signing_key_registry must be "
                    "TrustedAgentSigningKeyRegistry."
                )

            self._signing_secret: bytes | None = None
            self._signing_key_registry = (
                signing_key_registry
            )

            return

        if not isinstance(
            signing_secret,
            str,
        ):
            raise TypeError(
                "signing_secret must be str."
            )

        normalized_secret = signing_secret.strip()

        if not normalized_secret:
            raise ValueError(
                "signing_secret is required."
            )

        self._signing_secret = (
            normalized_secret.encode(
                "utf-8"
            )
        )

        self._signing_key_registry = None

    def _resolve_signing_secret(
        self,
        mission: ExecutionMission,
    ) -> bytes:
        if self._signing_key_registry is None:
            if self._signing_secret is None:
                raise RuntimeError(
                    "Execution mission signer "
                    "has no signing secret."
                )

            return self._signing_secret

        signing_secret = (
            self._signing_key_registry.get_secret(
                agent_id=mission.agent_id
            )
        )

        if signing_secret is None:
            raise ValueError(
                "Trusted Agent signing key not found."
            )

        return signing_secret.encode(
            "utf-8"
        )

    def sign(
        self,
        mission: ExecutionMission,
    ) -> str:
        payload = (
            ExecutionMissionSigningPayload.build(
                mission
            )
        )

        signing_secret = (
            self._resolve_signing_secret(
                mission
            )
        )

        return hmac.new(
            signing_secret,
            payload,
            hashlib.sha256,
        ).hexdigest()

    def verify(
        self,
        mission: ExecutionMission,
        signature: str,
    ) -> bool:
        if not isinstance(
            signature,
            str,
        ):
            return False

        normalized_signature = signature.strip()

        if not normalized_signature:
            return False

        expected_signature = self.sign(
            mission
        )

        return hmac.compare_digest(
            normalized_signature,
            expected_signature,
        )