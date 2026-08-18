"""
TODOBA Control Mission Signer V2

Creates and verifies integrity signatures for
ControlMission V2 payloads.

V2 uses the explicit control signing domain and
Cloud-owned security_sequence replay identity.

The legacy V1 signer remains unchanged.
"""

import hashlib
import hmac

from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_signing_payload_v2 import (
    ControlMissionSigningPayloadV2,
)


class ControlMissionSignerV2:
    """
    Sign and verify ControlMission V2 payload integrity.
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
            ControlMissionSigningPayloadV2.build(
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