"""
TODOBA Control Mission Signer

Creates and verifies integrity signatures for
ControlMission payloads.

Responsibilities:

- create HMAC-SHA256 signatures
- verify control mission signatures
- use the control signing payload domain

This component does not authenticate Trusted Agents,
provide replay protection, or control broker trades.
"""

import hashlib
import hmac

from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_signing_payload import (
    ControlMissionSigningPayload,
)


class ControlMissionSigner:
    """
    Sign and verify ControlMission payload integrity.
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
        mission: ControlMission,
    ) -> str:
        payload = (
            ControlMissionSigningPayload.build(
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
        mission: ControlMission,
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