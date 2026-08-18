"""
TODOBA Persistent Security Sequence Binding Store

Owns durable mission identity bindings for security
sequence allocation.

Responsibilities:
- bind mission_id to one source payload fingerprint
- preserve the assigned security_sequence
- reuse the existing sequence for identical retries
- reject mission_id reuse with different payload
- restore bindings after runtime restart
- persist through atomic temporary-file replacement

This component does not:
- allocate security sequences
- create missions
- own mission lifecycle records
- validate replay state inside Trusted Agents
"""

import json
import os
from pathlib import Path
from threading import Lock
from typing import Optional


class PersistentSecuritySequenceBindingStore:
    """
    Persist durable mission-to-security-sequence bindings.
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

        self._bindings = (
            self._restore_bindings()
        )

    def bind(
        self,
        *,
        mission_id: str,
        payload_fingerprint: str,
        security_sequence: int,
    ) -> int:
        """
        Create or reuse one durable mission binding.

        An identical mission retry reuses the original
        security sequence.

        Reusing the same mission_id with a different
        payload fingerprint is rejected.
        """

        self._validate_mission_id(
            mission_id
        )

        self._validate_payload_fingerprint(
            payload_fingerprint
        )

        self._validate_security_sequence(
            security_sequence
        )

        with self._lock:
            existing = self._bindings.get(
                mission_id
            )

            if existing is not None:
                if (
                    existing[
                        "payload_fingerprint"
                    ]
                    != payload_fingerprint
                ):
                    raise ValueError(
                        "mission_id already bound to "
                        "different payload."
                    )

                return existing[
                    "security_sequence"
                ]

            updated_bindings = dict(
                self._bindings
            )

            updated_bindings[
                mission_id
            ] = {
                "payload_fingerprint": (
                    payload_fingerprint
                ),
                "security_sequence": (
                    security_sequence
                ),
            }

            self._persist(
                updated_bindings
            )

            self._bindings = (
                updated_bindings
            )

            return security_sequence

    def get(
        self,
        mission_id: str,
    ) -> Optional[
        tuple[str, int]
    ]:
        self._validate_mission_id(
            mission_id
        )

        with self._lock:
            binding = self._bindings.get(
                mission_id
            )

            if binding is None:
                return None

            return (
                binding[
                    "payload_fingerprint"
                ],
                binding[
                    "security_sequence"
                ],
            )

    def _restore_bindings(
        self,
    ) -> dict[
        str,
        dict[str, str | int],
    ]:
        if not self.storage_path.exists():
            return {}

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
                "security sequence binding state "
                "must be object."
            )

        bindings = payload.get(
            "bindings"
        )

        if not isinstance(
            bindings,
            dict,
        ):
            raise ValueError(
                "security sequence binding state "
                "requires bindings."
            )

        restored: dict[
            str,
            dict[str, str | int],
        ] = {}

        for (
            mission_id,
            binding,
        ) in bindings.items():
            self._validate_mission_id(
                mission_id
            )

            if not isinstance(
                binding,
                dict,
            ):
                raise ValueError(
                    "security sequence binding "
                    "must be object."
                )

            if (
                "payload_fingerprint"
                not in binding
                or "security_sequence"
                not in binding
            ):
                raise ValueError(
                    "security sequence binding "
                    "is incomplete."
                )

            payload_fingerprint = (
                binding[
                    "payload_fingerprint"
                ]
            )

            security_sequence = (
                binding[
                    "security_sequence"
                ]
            )

            self._validate_payload_fingerprint(
                payload_fingerprint
            )

            self._validate_security_sequence(
                security_sequence
            )

            restored[
                mission_id
            ] = {
                "payload_fingerprint": (
                    payload_fingerprint
                ),
                "security_sequence": (
                    security_sequence
                ),
            }

        return restored

    def _persist(
        self,
        bindings: dict[
            str,
            dict[str, str | int],
        ],
    ) -> None:
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "bindings": bindings,
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
                sort_keys=True,
            )

            file.flush()
            os.fsync(
                file.fileno()
            )

        temporary_path.replace(
            self.storage_path
        )

    @staticmethod
    def _validate_mission_id(
        mission_id: str,
    ) -> None:
        if (
            not isinstance(
                mission_id,
                str,
            )
            or not mission_id.strip()
        ):
            raise ValueError(
                "mission_id must be "
                "a non-empty string."
            )

    @staticmethod
    def _validate_payload_fingerprint(
        payload_fingerprint: str,
    ) -> None:
        if (
            not isinstance(
                payload_fingerprint,
                str,
            )
            or not payload_fingerprint.strip()
        ):
            raise ValueError(
                "payload_fingerprint must be "
                "a non-empty string."
            )

    @staticmethod
    def _validate_security_sequence(
        security_sequence: int,
    ) -> None:
        if (
            not isinstance(
                security_sequence,
                int,
            )
            or isinstance(
                security_sequence,
                bool,
            )
            or security_sequence <= 0
        ):
            raise ValueError(
                "security_sequence must be "
                "a positive integer."
            )