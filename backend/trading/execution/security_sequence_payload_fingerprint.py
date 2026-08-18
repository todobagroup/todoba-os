"""
TODOBA Security Sequence Payload Fingerprint

Builds a deterministic SHA-256 fingerprint from a
JSON-safe mission source payload.

Responsibilities:
- canonicalize dictionary key ordering
- serialize deterministically as UTF-8 JSON
- produce a SHA-256 hexadecimal fingerprint

This component does not:
- decide which mission fields belong in the payload
- allocate security sequences
- persist mission bindings
- create execution or control missions
"""

import hashlib
import json
from typing import Any


class SecuritySequencePayloadFingerprint:
    """
    Build deterministic payload fingerprints.
    """

    @staticmethod
    def build(
        payload: dict[str, Any],
    ) -> str:
        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "payload must be dict."
            )

        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            canonical.encode(
                "utf-8"
            )
        ).hexdigest()