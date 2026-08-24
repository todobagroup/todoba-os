"""
TODOBA Trusted Agent Account Binding Store

Owns the authoritative Cloud binding between Trusted Agents
and MT5 account fingerprints.

Responsibilities:
- persist Agent-to-account ownership bindings
- reject conflicting re-binding
- accept identical binding retries idempotently
- persist state before advancing in-memory state
- restore durable bindings across Cloud restarts

This component does not:
- authenticate Trusted Agents
- receive HTTP requests
- manage replay floors
- allocate security sequences
- execute broker actions
"""

import json
import os
from pathlib import Path


STORE_VERSION = 1


class TrustedAgentAccountBindingStore:
    """
    Durable Trusted Agent account ownership registry.

    Identity:
        agent_id

    Authoritative value:
        account_fingerprint
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

        self._bindings: dict[
            str,
            str,
        ] = {}

        self._ready = False

        if self.storage_path.exists():
            self._restore_from_disk()

    def initialize_empty(
        self,
    ) -> None:
        """
        Explicitly initialize a new empty binding store.

        Missing durable storage is never silently
        interpreted as an empty authoritative registry.
        """

        if self._ready:
            return

        if self.storage_path.exists():
            self._restore_from_disk()
            return

        self._write_bindings(
            {}
        )

        self._bindings = {}
        self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def bind(
        self,
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> str:
        """
        Bind one Trusted Agent to one MT5 account.

        Rules:
        - first binding is accepted
        - identical retry is idempotent
        - same Agent with a different account is rejected
        - same MT5 account cannot belong to two Agents
        - durable state is written before RAM advances
        """

        self._require_ready()

        normalized_agent_id = (
            self._normalize_agent_id(
                agent_id
            )
        )

        normalized_account_fingerprint = (
            self._normalize_account_fingerprint(
                account_fingerprint
            )
        )

        existing = self._bindings.get(
            normalized_agent_id
        )

        if existing is not None:
            if (
                existing
                !=
                normalized_account_fingerprint
            ):
                raise ValueError(
                    "Trusted Agent is already bound "
                    "to a different account."
                )

            return existing

        existing_account_owner = (
            self.get_agent_id_for_account(
                account_fingerprint=(
                    normalized_account_fingerprint
                )
            )
        )

        if existing_account_owner is not None:
            raise ValueError(
                "MT5 account is already bound to a "
                "different Trusted Agent."
            )

        candidate = dict(
            self._bindings
        )

        candidate[
            normalized_agent_id
        ] = normalized_account_fingerprint

        self._write_bindings(
            candidate
        )

        self._bindings = candidate

        return normalized_account_fingerprint

    def get_account_fingerprint(
        self,
        *,
        agent_id: str,
    ) -> str | None:
        """
        Return the authoritative account fingerprint
        for one Trusted Agent.
        """

        self._require_ready()

        normalized_agent_id = (
            self._normalize_agent_id(
                agent_id
            )
        )

        return self._bindings.get(
            normalized_agent_id
        )

    def get_agent_id_for_account(
        self,
        *,
        account_fingerprint: str,
    ) -> str | None:
        """
        Return the authoritative Trusted Agent owner
        for one MT5 account fingerprint.

        Returns None when the account is not bound.
        """

        self._require_ready()

        normalized_account_fingerprint = (
            self._normalize_account_fingerprint(
                account_fingerprint
            )
        )

        for (
            agent_id,
            bound_account_fingerprint,
        ) in self._bindings.items():
            if (
                bound_account_fingerprint
                == normalized_account_fingerprint
            ):
                return agent_id

        return None

    def owns_account(
        self,
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> bool:
        """
        Return True only when the durable binding matches
        the supplied Agent/account pair.
        """

        self._require_ready()

        normalized_agent_id = (
            self._normalize_agent_id(
                agent_id
            )
        )

        normalized_account_fingerprint = (
            self._normalize_account_fingerprint(
                account_fingerprint
            )
        )

        existing = self._bindings.get(
            normalized_agent_id
        )

        if existing is None:
            return False

        return (
            existing
            ==
            normalized_account_fingerprint
        )

    def size(
        self,
    ) -> int:
        self._require_ready()

        return len(
            self._bindings
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Trusted Agent account binding store "
                "is not initialized."
            )

    @staticmethod
    def _normalize_agent_id(
        agent_id: str,
    ) -> str:
        if not isinstance(
            agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be str."
            )

        normalized = agent_id.strip()

        if not normalized:
            raise ValueError(
                "agent_id must not be empty."
            )

        return normalized

    @staticmethod
    def _normalize_account_fingerprint(
        account_fingerprint: str,
    ) -> str:
        if not isinstance(
            account_fingerprint,
            str,
        ):
            raise TypeError(
                "account_fingerprint must be str."
            )

        normalized = (
            account_fingerprint.strip()
        )

        if not normalized:
            raise ValueError(
                "account_fingerprint must not be empty."
            )

        return normalized

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
                "Trusted Agent account binding payload "
                "must be an object."
            )

        version = payload.get(
            "version"
        )

        if version != STORE_VERSION:
            raise ValueError(
                "Unsupported Trusted Agent account "
                "binding store version."
            )

        items = payload.get(
            "bindings"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Trusted Agent account binding payload "
                "bindings must be a list."
            )

        restored: dict[
            str,
            str,
        ] = {}

        seen_account_fingerprints: set[
            str
        ] = set()

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Trusted Agent account binding item "
                    "must be an object."
                )

            if set(
                item.keys()
            ) != {
                "agent_id",
                "account_fingerprint",
            }:
                raise ValueError(
                    "Trusted Agent account binding item "
                    "has invalid fields."
                )

            agent_id = (
                self._normalize_agent_id(
                    item[
                        "agent_id"
                    ]
                )
            )

            account_fingerprint = (
                self._normalize_account_fingerprint(
                    item[
                        "account_fingerprint"
                    ]
                )
            )

            if agent_id in restored:
                raise ValueError(
                    "Duplicate Trusted Agent "
                    "account binding."
                )

            if (
                account_fingerprint
                in seen_account_fingerprints
            ):
                raise ValueError(
                    "MT5 account is bound to multiple "
                    "Trusted Agents."
                )

            restored[
                agent_id
            ] = account_fingerprint

            seen_account_fingerprints.add(
                account_fingerprint
            )

        self._bindings = restored
        self._ready = True

    def _write_bindings(
        self,
        bindings: dict[
            str,
            str,
        ],
    ) -> None:
        items = []

        for agent_id in sorted(
            bindings
        ):
            items.append(
                {
                    "agent_id": agent_id,
                    "account_fingerprint": (
                        bindings[
                            agent_id
                        ]
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "bindings": items,
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