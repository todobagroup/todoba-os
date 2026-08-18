"""
TODOBA Security Sequence Assignment Service

Coordinates durable security sequence assignment for
mission source identities.

Responsibilities:
- fingerprint the source mission payload
- reuse an existing durable binding for identical retries
- reject mission_id reuse with a different payload
- allocate a new security sequence only for a new mission
- serialize assignment inside one runtime to prevent
  duplicate allocation during concurrent retries

This component does not:
- create execution or control missions
- own mission lifecycle records
- sign missions
- validate replay state inside Trusted Agents
"""

from threading import Lock
from typing import Any

from backend.trading.execution.persistent_security_sequence_allocator import (
    PersistentSecuritySequenceAllocator,
)
from backend.trading.execution.persistent_security_sequence_binding_store import (
    PersistentSecuritySequenceBindingStore,
)
from backend.trading.execution.security_sequence_payload_fingerprint import (
    SecuritySequencePayloadFingerprint,
)


class SecuritySequenceAssignmentService:
    """
    Coordinate durable mission security sequence assignment.
    """

    def __init__(
        self,
        *,
        allocator: PersistentSecuritySequenceAllocator,
        binding_store: PersistentSecuritySequenceBindingStore,
    ) -> None:
        self.allocator = allocator
        self.binding_store = binding_store
        self._lock = Lock()

    def assign(
        self,
        *,
        mission_id: str,
        source_payload: dict[str, Any],
    ) -> int:
        """
        Assign or reuse one durable security sequence.

        Identical retries reuse the original sequence.
        Conflicting payload reuse is rejected before any
        new sequence is allocated.
        """

        fingerprint = (
            SecuritySequencePayloadFingerprint.build(
                source_payload
            )
        )

        with self._lock:
            existing = self.binding_store.get(
                mission_id
            )

            if existing is not None:
                (
                    existing_fingerprint,
                    existing_sequence,
                ) = existing

                if (
                    existing_fingerprint
                    != fingerprint
                ):
                    raise ValueError(
                        "mission_id already bound to "
                        "different payload."
                    )

                return existing_sequence

            security_sequence = (
                self.allocator.allocate()
            )

            return self.binding_store.bind(
                mission_id=mission_id,
                payload_fingerprint=fingerprint,
                security_sequence=(
                    security_sequence
                ),
            )