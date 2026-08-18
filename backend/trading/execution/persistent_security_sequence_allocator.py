"""
TODOBA Persistent Security Sequence Allocator

Owns one persistent monotonic security sequence.

Responsibilities:
- allocate strictly increasing security sequences
- persist the latest allocated sequence
- restore sequence state after runtime restart
- persist through atomic temporary-file replacement

This component does not:
- create execution or control missions
- own source message sequences
- own mission lifecycle records
- perform replay validation inside Trusted Agents
"""

import json
import os
from pathlib import Path
from threading import Lock


class PersistentSecuritySequenceAllocator:
    """
    Allocate one persistent monotonic sequence domain.

    Separate allocator instances with separate storage
    paths represent independent security sequence domains.
    """

    def __init__(
        self,
        storage_path: Path,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        self.storage_path = storage_path
        self._lock = Lock()

        self._current_sequence = (
            self._restore_current_sequence()
        )

    @property
    def current_sequence(
        self,
    ) -> int:
        with self._lock:
            return self._current_sequence

    def allocate(
        self,
    ) -> int:
        """
        Allocate and durably persist the next sequence.

        The in-memory sequence advances only after the
        new value has been persisted successfully.
        """

        with self._lock:
            next_sequence = (
                self._current_sequence
                + 1
            )

            self._persist(
                next_sequence
            )

            self._current_sequence = (
                next_sequence
            )

            return next_sequence

    def _restore_current_sequence(
        self,
    ) -> int:
        if not self.storage_path.exists():
            return 0

        payload = json.loads(
            self.storage_path.read_text(
                encoding="utf-8",
            )
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "security sequence state must be object."
            )

        if "current_sequence" not in payload:
            raise ValueError(
                "security sequence state requires "
                "current_sequence."
            )

        current_sequence = payload[
            "current_sequence"
        ]

        if (
            not isinstance(
                current_sequence,
                int,
            )
            or isinstance(
                current_sequence,
                bool,
            )
            or current_sequence < 0
        ):
            raise ValueError(
                "current_sequence must be "
                "a non-negative integer."
            )

        return current_sequence

    def _persist(
        self,
        sequence: int,
    ) -> None:
        if (
            not isinstance(
                sequence,
                int,
            )
            or isinstance(
                sequence,
                bool,
            )
            or sequence <= 0
        ):
            raise ValueError(
                "sequence must be a positive integer."
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "current_sequence": sequence,
        }

        temporary_path = (
            self.storage_path.with_suffix(
                self.storage_path.suffix
                + ".tmp"
            )
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                payload,
                file,
                indent=2,
            )

            file.flush()
            os.fsync(
                file.fileno()
            )

        temporary_path.replace(
            self.storage_path
        )