from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path


_STORE_VERSION = 1


@dataclass(
    frozen=True,
)
class CustomerCommercialDeploymentBinding:
    """
    Durable immutable binding between one purchased commercial
    entitlement and one authoritative customer deployment.

    This owner carries deployment/account identity only.
    It does not own commercial cap/price, payment, Setup state,
    deployment entitlement state, or runtime authorization.
    """

    commercial_entitlement_id: str
    customer_id: str
    deployment_id: str
    agent_id: str
    account_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        for field_name in (
            "commercial_entitlement_id",
            "customer_id",
            "deployment_id",
            "agent_id",
            "account_fingerprint",
        ):
            value = getattr(
                self,
                field_name,
            )

            object.__setattr__(
                self,
                field_name,
                self._normalize_required_string(
                    value,
                    name=field_name,
                ),
            )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} must not be empty."
            )

        return normalized


class CustomerCommercialDeploymentBindingStore:
    """
    Durable immutable commercial-entitlement ? deployment binding.

    Unique identities:
        commercial_entitlement_id
        deployment_id
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

        self._by_entitlement_id: dict[
            str,
            CustomerCommercialDeploymentBinding,
        ] = {}

        self._entitlement_id_by_deployment_id: dict[
            str,
            str,
        ] = {}

        self._ready = False
        self._lock = threading.RLock()

        if self.storage_path.exists():
            self.open_existing()

    def initialize_empty(
        self,
    ) -> None:
        with self._lock:
            if self.storage_path.exists():
                raise RuntimeError(
                    "Commercial deployment binding store "
                    "already exists."
                )

            self.storage_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._persist(
                {}
            )

            self._by_entitlement_id = {}
            self._entitlement_id_by_deployment_id = {}
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if not self.storage_path.exists():
                raise RuntimeError(
                    "Commercial deployment binding store "
                    "does not exist."
                )

            try:
                payload = json.loads(
                    self.storage_path.read_text(
                        encoding="utf-8",
                    )
                )
            except (
                OSError,
                json.JSONDecodeError,
            ) as exc:
                raise RuntimeError(
                    "Commercial deployment binding store "
                    "could not be opened."
                ) from exc

            if (
                not isinstance(
                    payload,
                    dict,
                )
                or set(
                    payload
                )
                != {
                    "version",
                    "bindings",
                }
                or payload.get(
                    "version"
                )
                != _STORE_VERSION
                or not isinstance(
                    payload.get(
                        "bindings"
                    ),
                    list,
                )
            ):
                raise RuntimeError(
                    "Commercial deployment binding store "
                    "payload is invalid."
                )

            restored: dict[
                str,
                CustomerCommercialDeploymentBinding,
            ] = {}

            deployment_index: dict[
                str,
                str,
            ] = {}

            for raw in payload[
                "bindings"
            ]:
                if (
                    not isinstance(
                        raw,
                        dict,
                    )
                    or set(
                        raw
                    )
                    != {
                        "commercial_entitlement_id",
                        "customer_id",
                        "deployment_id",
                        "agent_id",
                        "account_fingerprint",
                    }
                ):
                    raise RuntimeError(
                        "Commercial deployment binding "
                        "record payload is invalid."
                    )

                try:
                    binding = (
                        CustomerCommercialDeploymentBinding(
                            commercial_entitlement_id=raw[
                                "commercial_entitlement_id"
                            ],
                            customer_id=raw[
                                "customer_id"
                            ],
                            deployment_id=raw[
                                "deployment_id"
                            ],
                            agent_id=raw[
                                "agent_id"
                            ],
                            account_fingerprint=raw[
                                "account_fingerprint"
                            ],
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ) as exc:
                    raise RuntimeError(
                        "Commercial deployment binding "
                        "record payload is invalid."
                    ) from exc

                if (
                    binding.commercial_entitlement_id
                    in restored
                ):
                    raise RuntimeError(
                        "Duplicate commercial entitlement "
                        "binding identity."
                    )

                if (
                    binding.deployment_id
                    in deployment_index
                ):
                    raise RuntimeError(
                        "Duplicate deployment binding identity."
                    )

                restored[
                    binding.commercial_entitlement_id
                ] = binding

                deployment_index[
                    binding.deployment_id
                ] = binding.commercial_entitlement_id

            self._by_entitlement_id = restored
            self._entitlement_id_by_deployment_id = (
                deployment_index
            )
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        with self._lock:
            return self._ready

    def register(
        self,
        binding: CustomerCommercialDeploymentBinding,
    ) -> CustomerCommercialDeploymentBinding:
        if not isinstance(
            binding,
            CustomerCommercialDeploymentBinding,
        ):
            raise TypeError(
                "Commercial deployment binding store "
                "requires "
                "CustomerCommercialDeploymentBinding."
            )

        with self._lock:
            self._require_ready()

            existing = self._by_entitlement_id.get(
                binding.commercial_entitlement_id
            )

            if existing is not None:
                if existing != binding:
                    raise ValueError(
                        "entitlement is already bound "
                        "to different deployment truth."
                    )

                return existing

            existing_entitlement_id = (
                self._entitlement_id_by_deployment_id.get(
                    binding.deployment_id
                )
            )

            if existing_entitlement_id is not None:
                raise ValueError(
                    "deployment is already bound "
                    "to a commercial entitlement."
                )

            candidate = dict(
                self._by_entitlement_id
            )

            candidate[
                binding.commercial_entitlement_id
            ] = binding

            self._persist(
                candidate
            )

            deployment_index = dict(
                self._entitlement_id_by_deployment_id
            )

            deployment_index[
                binding.deployment_id
            ] = binding.commercial_entitlement_id

            self._by_entitlement_id = candidate
            self._entitlement_id_by_deployment_id = (
                deployment_index
            )

            return binding

    def get_by_entitlement_id(
        self,
        *,
        commercial_entitlement_id: str,
    ) -> CustomerCommercialDeploymentBinding | None:
        normalized = (
            CustomerCommercialDeploymentBinding
            ._normalize_required_string(
                commercial_entitlement_id,
                name="commercial_entitlement_id",
            )
        )

        with self._lock:
            self._require_ready()

            return self._by_entitlement_id.get(
                normalized
            )

    def get_by_deployment_id(
        self,
        *,
        deployment_id: str,
    ) -> CustomerCommercialDeploymentBinding | None:
        normalized = (
            CustomerCommercialDeploymentBinding
            ._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        with self._lock:
            self._require_ready()

            entitlement_id = (
                self._entitlement_id_by_deployment_id.get(
                    normalized
                )
            )

            if entitlement_id is None:
                return None

            return self._by_entitlement_id[
                entitlement_id
            ]

    def get_by_agent_account(
        self,
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> CustomerCommercialDeploymentBinding | None:
        normalized_agent_id = (
            CustomerCommercialDeploymentBinding
            ._normalize_required_string(
                agent_id,
                name="agent_id",
            )
        )

        normalized_account_fingerprint = (
            CustomerCommercialDeploymentBinding
            ._normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        with self._lock:
            self._require_ready()

            matches = tuple(
                binding
                for binding in self._by_entitlement_id.values()
                if (
                    binding.agent_id
                    == normalized_agent_id
                    and binding.account_fingerprint
                    == normalized_account_fingerprint
                )
            )

            if not matches:
                return None

            if len(matches) != 1:
                raise RuntimeError(
                    "Commercial deployment binding "
                    "agent/account authority is ambiguous."
                )

            return matches[0]

    def all(
        self,
    ) -> tuple[
        CustomerCommercialDeploymentBinding,
        ...,
    ]:
        with self._lock:
            self._require_ready()

            return tuple(
                self._by_entitlement_id[
                    entitlement_id
                ]
                for entitlement_id in sorted(
                    self._by_entitlement_id
                )
            )

    def size(
        self,
    ) -> int:
        with self._lock:
            self._require_ready()

            return len(
                self._by_entitlement_id
            )

    def _persist(
        self,
        bindings: dict[
            str,
            CustomerCommercialDeploymentBinding,
        ],
    ) -> None:
        payload = {
            "version": _STORE_VERSION,
            "bindings": [
                {
                    "commercial_entitlement_id": (
                        bindings[
                            entitlement_id
                        ].commercial_entitlement_id
                    ),
                    "customer_id": (
                        bindings[
                            entitlement_id
                        ].customer_id
                    ),
                    "deployment_id": (
                        bindings[
                            entitlement_id
                        ].deployment_id
                    ),
                    "agent_id": (
                        bindings[
                            entitlement_id
                        ].agent_id
                    ),
                    "account_fingerprint": (
                        bindings[
                            entitlement_id
                        ].account_fingerprint
                    ),
                }
                for entitlement_id in sorted(
                    bindings
                )
            ],
        }

        encoded = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.storage_path.with_name(
                f"{self.storage_path.name}.tmp"
            )
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(
                    encoded
                )
                handle.flush()
                os.fsync(
                    handle.fileno()
                )

            os.replace(
                temporary_path,
                self.storage_path,
            )
        except OSError as exc:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise RuntimeError(
                "Commercial deployment binding store "
                "could not be persisted."
            ) from exc

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Commercial deployment binding store "
                "is not initialized."
            )
