"""
TODOBA Persistent Replay Floor Store

Owns the authoritative Cloud replay floor for Trusted Agents.

Responsibilities:
- persist the highest committed security sequence
- scope floors by Agent and MT5 account fingerprint
- enforce monotonic replay floors
- accept identical retries idempotently
- persist state before advancing in-memory state
- restore durable state across Cloud restarts

This component does not:
- allocate security sequences
- deliver missions
- receive HTTP requests
- execute broker actions
- decide Execution or Control protocol policy

Execution and Control must use separate store instances
and separate storage paths.
"""

import json
import os
from pathlib import Path


STORE_VERSION = 1


class PersistentReplayFloorStore:
    """
    Durable replay floor ledger.

    Each store instance represents one security domain.

    Identity:
        agent_id + account_fingerprint

    Value:
        highest committed security_sequence
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

        self._floors: dict[
            tuple[str, str],
            int,
        ] = {}

        self._ready = False

        if self.storage_path.exists():
            self._restore_from_disk()

    def initialize_empty(
        self,
    ) -> None:
        """
        Explicitly initialize a new empty ledger.

        Missing storage is never silently interpreted as
        an empty authoritative replay floor.

        This method is intended only for controlled first
        provisioning of a new security domain.
        """

        if self._ready:
            return

        if self.storage_path.exists():
            self._restore_from_disk()
            return

        self._write_floors(
            {}
        )

        self._floors = {}
        self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def get_floor(
        self,
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> int:
        """
        Return the current committed replay floor.

        A ready ledger with no entry for this identity
        returns zero, meaning no security sequence has yet
        been committed for that Agent/account pair.
        """

        self._require_ready()

        identity = self._build_identity(
            agent_id=agent_id,
            account_fingerprint=account_fingerprint,
        )

        return self._floors.get(
            identity,
            0,
        )

    def commit_floor(
        self,
        *,
        agent_id: str,
        account_fingerprint: str,
        security_sequence: int,
    ) -> int:
        """
        Commit a new authoritative replay floor.

        Rules:
        - sequence must be a positive integer
        - equal retry is idempotent
        - lower sequence is rejected
        - higher sequence is persisted before RAM advances
        """

        self._require_ready()

        identity = self._build_identity(
            agent_id=agent_id,
            account_fingerprint=account_fingerprint,
        )

        self._validate_security_sequence(
            security_sequence
        )

        current_floor = self._floors.get(
            identity,
            0,
        )

        if security_sequence == current_floor:
            return current_floor

        if security_sequence < current_floor:
            raise ValueError(
                "security_sequence cannot move "
                "replay floor backwards."
            )

        candidate = dict(
            self._floors
        )

        candidate[
            identity
        ] = security_sequence

        self._write_floors(
            candidate
        )

        self._floors = candidate

        return security_sequence

    def size(
        self,
    ) -> int:
        self._require_ready()

        return len(
            self._floors
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Persistent replay floor store "
                "is not initialized."
            )

    @staticmethod
    def _build_identity(
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> tuple[str, str]:
        if not isinstance(
            agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be str."
            )

        if not agent_id.strip():
            raise ValueError(
                "agent_id must not be empty."
            )

        if not isinstance(
            account_fingerprint,
            str,
        ):
            raise TypeError(
                "account_fingerprint must be str."
            )

        if not account_fingerprint.strip():
            raise ValueError(
                "account_fingerprint must not be empty."
            )

        return (
            agent_id.strip(),
            account_fingerprint.strip(),
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
        ):
            raise TypeError(
                "security_sequence must be int."
            )

        if security_sequence <= 0:
            raise ValueError(
                "security_sequence must be positive."
            )

    def _restore_from_disk(
        self,
    ) -> None:
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
                "Replay floor payload must be an object."
            )

        version = payload.get(
            "version"
        )

        if version != STORE_VERSION:
            raise ValueError(
                "Unsupported replay floor store version."
            )

        items = payload.get(
            "floors"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Replay floor payload floors "
                "must be a list."
            )

        restored: dict[
            tuple[str, str],
            int,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Replay floor item must be an object."
                )

            if set(
                item.keys()
            ) != {
                "agent_id",
                "account_fingerprint",
                "security_sequence",
            }:
                raise ValueError(
                    "Replay floor item has invalid fields."
                )

            identity = self._build_identity(
                agent_id=item[
                    "agent_id"
                ],
                account_fingerprint=item[
                    "account_fingerprint"
                ],
            )

            security_sequence = item[
                "security_sequence"
            ]

            self._validate_security_sequence(
                security_sequence
            )

            if identity in restored:
                raise ValueError(
                    "Duplicate replay floor identity."
                )

            restored[
                identity
            ] = security_sequence

        self._floors = restored
        self._ready = True

    def _write_floors(
        self,
        floors: dict[
            tuple[str, str],
            int,
        ],
    ) -> None:
        items = []

        for (
            agent_id,
            account_fingerprint,
        ), security_sequence in sorted(
            floors.items()
        ):
            items.append(
                {
                    "agent_id": agent_id,
                    "account_fingerprint": (
                        account_fingerprint
                    ),
                    "security_sequence": (
                        security_sequence
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "floors": items,
        }

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = Path(
            f"{self.storage_path}.tmp"
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file_handle:
            json.dump(
                payload,
                file_handle,
                indent=2,
                sort_keys=True,
            )

            file_handle.write(
                "\n"
            )

            file_handle.flush()

            os.fsync(
                file_handle.fileno()
            )

        os.replace(
            temporary_path,
            self.storage_path,
        )