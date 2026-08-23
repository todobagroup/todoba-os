"""
TODOBA Customer Deployment Registry

Owns the durable commercial identity relationship between
customers and their TODOBA Trading deployments.

Responsibilities:
- register customer deployment identities
- persist deployments before advancing in-memory state
- restore deployments across Cloud restarts
- accept identical registration idempotently
- reject conflicting deployment identity
- reject one Agent identity being assigned to two deployments

This component does not:
- store Trusted Agent secrets
- store mission signing secrets
- own MT5 account bindings
- own trading activation
- own subscription or entitlement
- execute trading actions
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path


STORE_VERSION = 1


@dataclass(frozen=True)
class CustomerDeployment:
    """
    Immutable commercial deployment identity.

    One customer may own multiple deployments.

    One deployment owns exactly one Trusted Agent identity.
    """

    customer_id: str
    deployment_id: str
    agent_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "customer_id",
            self._normalize_required_string(
                self.customer_id,
                name="customer_id",
            ),
        )

        object.__setattr__(
            self,
            "deployment_id",
            self._normalize_required_string(
                self.deployment_id,
                name="deployment_id",
            ),
        )

        object.__setattr__(
            self,
            "agent_id",
            self._normalize_required_string(
                self.agent_id,
                name="agent_id",
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
                f"{name} is required."
            )

        return normalized


class CustomerDeploymentRegistry:
    """
    Durable registry of customer deployment identities.

    Identity:
        deployment_id

    Additional uniqueness:
        agent_id

    Customer identity may repeat because one customer can
    own multiple MT5 deployments.
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

        self._deployments: dict[
            str,
            CustomerDeployment,
        ] = {}

        self._deployment_ids_by_agent_id: dict[
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
        Explicitly initialize a new empty registry.

        Missing durable storage is never silently treated
        as initialized commercial state.
        """

        if self._ready:
            return

        if self.storage_path.exists():
            self._restore_from_disk()
            return

        self._write_deployments(
            {}
        )

        self._deployments = {}
        self._deployment_ids_by_agent_id = {}
        self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        deployment: CustomerDeployment,
    ) -> CustomerDeployment:
        """
        Register one customer deployment.

        Rules:
        - first registration is accepted
        - identical retry is idempotent
        - conflicting deployment identity is rejected
        - one Agent cannot belong to two deployments
        - durable state is written before RAM advances
        """

        self._require_ready()

        if not isinstance(
            deployment,
            CustomerDeployment,
        ):
            raise TypeError(
                "CustomerDeploymentRegistry requires "
                "CustomerDeployment."
            )

        existing = self._deployments.get(
            deployment.deployment_id
        )

        if existing is not None:
            if existing != deployment:
                raise ValueError(
                    "Customer deployment is already "
                    "registered with different identity."
                )

            return existing

        existing_deployment_id = (
            self._deployment_ids_by_agent_id.get(
                deployment.agent_id
            )
        )

        if existing_deployment_id is not None:
            raise ValueError(
                "Trusted Agent identity is already assigned "
                "to another customer deployment."
            )

        candidate = dict(
            self._deployments
        )

        candidate[
            deployment.deployment_id
        ] = deployment

        self._write_deployments(
            candidate
        )

        candidate_agent_index = dict(
            self._deployment_ids_by_agent_id
        )

        candidate_agent_index[
            deployment.agent_id
        ] = deployment.deployment_id

        self._deployments = candidate
        self._deployment_ids_by_agent_id = (
            candidate_agent_index
        )

        return deployment

    def get(
        self,
        *,
        deployment_id: str,
    ) -> CustomerDeployment | None:
        self._require_ready()

        normalized_deployment_id = (
            self._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        return self._deployments.get(
            normalized_deployment_id
        )

    def get_by_agent_id(
        self,
        *,
        agent_id: str,
    ) -> CustomerDeployment | None:
        self._require_ready()

        normalized_agent_id = (
            self._normalize_required_string(
                agent_id,
                name="agent_id",
            )
        )

        deployment_id = (
            self._deployment_ids_by_agent_id.get(
                normalized_agent_id
            )
        )

        if deployment_id is None:
            return None

        return self._deployments[
            deployment_id
        ]

    def all(
        self,
    ) -> tuple[
        CustomerDeployment,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._deployments[
                deployment_id
            ]
            for deployment_id in sorted(
                self._deployments
            )
        )

    def size(
        self,
    ) -> int:
        self._require_ready()

        return len(
            self._deployments
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer deployment registry "
                "is not initialized."
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
                f"{name} is required."
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
                "Customer deployment registry payload "
                "must be an object."
            )

        version = payload.get(
            "version"
        )

        if version != STORE_VERSION:
            raise ValueError(
                "Unsupported customer deployment "
                "registry version."
            )

        items = payload.get(
            "deployments"
        )

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer deployment registry payload "
                "deployments must be a list."
            )

        restored: dict[
            str,
            CustomerDeployment,
        ] = {}

        restored_agent_index: dict[
            str,
            str,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer deployment item "
                    "must be an object."
                )

            if set(
                item.keys()
            ) != {
                "customer_id",
                "deployment_id",
                "agent_id",
            }:
                raise ValueError(
                    "Customer deployment item "
                    "has invalid fields."
                )

            deployment = CustomerDeployment(
                customer_id=item[
                    "customer_id"
                ],
                deployment_id=item[
                    "deployment_id"
                ],
                agent_id=item[
                    "agent_id"
                ],
            )

            if (
                deployment.deployment_id
                in restored
            ):
                raise ValueError(
                    "Duplicate customer deployment."
                )

            if (
                deployment.agent_id
                in restored_agent_index
            ):
                raise ValueError(
                    "Duplicate Trusted Agent identity "
                    "across customer deployments."
                )

            restored[
                deployment.deployment_id
            ] = deployment

            restored_agent_index[
                deployment.agent_id
            ] = deployment.deployment_id

        self._deployments = restored
        self._deployment_ids_by_agent_id = (
            restored_agent_index
        )
        self._ready = True

    def _write_deployments(
        self,
        deployments: dict[
            str,
            CustomerDeployment,
        ],
    ) -> None:
        items = []

        for deployment_id in sorted(
            deployments
        ):
            deployment = deployments[
                deployment_id
            ]

            items.append(
                {
                    "customer_id": (
                        deployment.customer_id
                    ),
                    "deployment_id": (
                        deployment.deployment_id
                    ),
                    "agent_id": (
                        deployment.agent_id
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "deployments": items,
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
