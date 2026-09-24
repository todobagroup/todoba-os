"""
TODOBA Legacy Execution Compatibility Registry.

Durable explicit eligibility for customer deployments
approved through a sanctioned compatibility recovery path.

Identity:
    deployment_id

Stored provenance:
    setup_activation_id
    recovery_request_id

This owner does not:
- decide whether a deployment is eligible
- infer legacy status from deployment entitlement
- process payment, settlement, or commercial capacity
- authorize execution missions
- create customer deployments
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import uuid

from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)


STORE_VERSION = 1


@dataclass(frozen=True)
class CustomerLegacyExecutionCompatibilityRecord:
    deployment_id: str
    setup_activation_id: str
    recovery_request_id: str

    def __post_init__(self) -> None:
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
            "setup_activation_id",
            self._normalize_required_string(
                self.setup_activation_id,
                name="setup_activation_id",
            ),
        )
        object.__setattr__(
            self,
            "recovery_request_id",
            self._normalize_required_string(
                self.recovery_request_id,
                name="recovery_request_id",
            ),
        )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} must not be empty."
            )

        return normalized


class CustomerLegacyExecutionCompatibilityRegistry:
    """
    Durable explicit compatibility eligibility registry.

    Absence means not eligible.
    """

    def __init__(
        self,
        storage_path: Path,
        *,
        deployment_registry: CustomerDeploymentRegistry,
    ) -> None:
        if not isinstance(
            storage_path,
            Path,
        ):
            raise TypeError(
                "storage_path must be Path."
            )

        if not isinstance(
            deployment_registry,
            CustomerDeploymentRegistry,
        ):
            raise TypeError(
                "deployment_registry must be "
                "CustomerDeploymentRegistry."
            )

        if not deployment_registry.is_ready():
            raise ValueError(
                "deployment_registry must be ready."
            )

        self.storage_path = storage_path
        self._deployment_registry = deployment_registry

        self._records: dict[
            str,
            CustomerLegacyExecutionCompatibilityRecord,
        ] = {}

        self._ready = False

        if self.storage_path.exists():
            self._restore_from_disk()

    def initialize_empty(
        self,
    ) -> None:
        if self._ready:
            raise ValueError(
                "Customer legacy execution compatibility "
                "registry is already ready."
            )

        candidate: dict[
            str,
            CustomerLegacyExecutionCompatibilityRecord,
        ] = {}

        self._write_records(
            candidate
        )

        self._records = candidate
        self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        record: CustomerLegacyExecutionCompatibilityRecord,
    ) -> CustomerLegacyExecutionCompatibilityRecord:
        self._require_ready()

        if not isinstance(
            record,
            CustomerLegacyExecutionCompatibilityRecord,
        ):
            raise TypeError(
                "CustomerLegacyExecutionCompatibilityRegistry "
                "requires "
                "CustomerLegacyExecutionCompatibilityRecord."
            )

        deployment = self._deployment_registry.get(
            deployment_id=record.deployment_id,
        )

        if deployment is None:
            raise ValueError(
                "Customer deployment does not exist."
            )

        existing = self._records.get(
            deployment.deployment_id
        )

        if existing is not None:
            if existing != record:
                raise ValueError(
                    "Customer legacy execution compatibility "
                    "is already registered with different "
                    "recovery provenance."
                )

            return existing

        candidate = dict(
            self._records
        )

        candidate[
            deployment.deployment_id
        ] = record

        self._write_records(
            candidate
        )

        self._records = candidate

        return record

    def get(
        self,
        *,
        deployment_id: str,
    ) -> CustomerLegacyExecutionCompatibilityRecord | None:
        self._require_ready()

        normalized_deployment_id = (
            self._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        return self._records.get(
            normalized_deployment_id
        )

    def size(
        self,
    ) -> int:
        self._require_ready()

        return len(
            self._records
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Customer legacy execution compatibility "
                "registry is not initialized."
            )

    def _restore_from_disk(
        self,
    ) -> None:
        try:
            payload = json.loads(
                self.storage_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "Customer legacy execution compatibility "
                "store is unreadable."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer legacy execution compatibility "
                "store must contain an object."
            )

        if set(
            payload
        ) != {
            "version",
            "records",
        }:
            raise ValueError(
                "Customer legacy execution compatibility "
                "store has invalid fields."
            )

        if payload[
            "version"
        ] != STORE_VERSION:
            raise ValueError(
                "Unsupported customer legacy execution "
                "compatibility store version."
            )

        items = payload[
            "records"
        ]

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer legacy execution compatibility "
                "records must be a list."
            )

        restored: dict[
            str,
            CustomerLegacyExecutionCompatibilityRecord,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer legacy execution compatibility "
                    "record must be an object."
                )

            if set(
                item
            ) != {
                "deployment_id",
                "setup_activation_id",
                "recovery_request_id",
            }:
                raise ValueError(
                    "Customer legacy execution compatibility "
                    "record has invalid fields."
                )

            try:
                record = (
                    CustomerLegacyExecutionCompatibilityRecord(
                        deployment_id=item[
                            "deployment_id"
                        ],
                        setup_activation_id=item[
                            "setup_activation_id"
                        ],
                        recovery_request_id=item[
                            "recovery_request_id"
                        ],
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Customer legacy execution compatibility "
                    "record is invalid."
                ) from exc

            if record.deployment_id in restored:
                raise ValueError(
                    "Duplicate customer legacy execution "
                    "compatibility record."
                )

            try:
                deployment = (
                    self._deployment_registry.get(
                        deployment_id=(
                            record.deployment_id
                        )
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Customer legacy execution compatibility "
                    "references invalid deployment."
                ) from exc

            if deployment is None:
                raise ValueError(
                    "Customer legacy execution compatibility "
                    "references unknown deployment."
                )

            restored[
                record.deployment_id
            ] = record

        self._records = restored
        self._ready = True

    def _write_records(
        self,
        records: dict[
            str,
            CustomerLegacyExecutionCompatibilityRecord,
        ],
    ) -> None:
        items = []

        for deployment_id in sorted(
            records
        ):
            record = records[
                deployment_id
            ]

            items.append(
                {
                    "deployment_id": (
                        record.deployment_id
                    ),
                    "setup_activation_id": (
                        record.setup_activation_id
                    ),
                    "recovery_request_id": (
                        record.recovery_request_id
                    ),
                }
            )

        payload = {
            "version": STORE_VERSION,
            "records": items,
        }

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.storage_path.with_name(
                self.storage_path.name
                + "."
                + uuid.uuid4().hex
                + ".tmp"
            )
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as destination:
                json.dump(
                    payload,
                    destination,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )

                destination.write(
                    "\n"
                )

                destination.flush()
                os.fsync(
                    destination.fileno()
                )

            os.replace(
                temporary_path,
                self.storage_path,
            )
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

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
