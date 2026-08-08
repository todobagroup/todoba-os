"""
TODOBA Execution Mission Signer

Creates and verifies integrity signatures for
ExecutionMission payloads.

Responsibilities:

- create HMAC-SHA256 signatures
- verify mission signatures
- use the cross-language signing payload contract

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


class ExecutionMissionSigner:
    """
    Sign and verify ExecutionMission payload integrity.
    """

    def __init__(
        self,
        signing_secret: str,
    ) -> None:
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

    def sign(
        self,
        mission: ExecutionMission,
    ) -> str:
        payload = (
            ExecutionMissionSigningPayload.build(
                mission
            )
        )

        return hmac.new(
            self._signing_secret,
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