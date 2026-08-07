"""
TODOBA Execution Mission Evidence Idempotency Registry

Tracks execution mission evidence identities
that have already been accepted.

Responsibilities:
- accept new evidence identities
- reject duplicate evidence identities
- report identity membership and registry size

This component does not:
- build evidence identities
- persist evidence
- receive HTTP requests
- modify mission lifecycle
"""

class ExecutionMissionEvidenceIdempotencyRegistry:
    """
    In-memory registry of accepted evidence identities.
    """

    def __init__(
        self,
    ) -> None:
        self._identities: set[str] = set()

    def accept(
        self,
        identity: str,
    ) -> bool:
        if not isinstance(
            identity,
            str,
        ):
            raise TypeError(
                "identity must be str."
            )

        if not identity:
            raise ValueError(
                "identity must not be empty."
            )

        if identity in self._identities:
            return False

        self._identities.add(
            identity
        )

        return True

    def contains(
        self,
        identity: str,
    ) -> bool:
        if not isinstance(
            identity,
            str,
        ):
            raise TypeError(
                "identity must be str."
            )

        return identity in self._identities

    def size(
        self,
    ) -> int:
        return len(
            self._identities
        )