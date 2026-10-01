"""
TODOBA Manual Commercial Activation Authority.

This capability represents an explicit authenticated commercial
operator approval that is independent of payment settlement.

It does NOT:
- create or mutate payment intent
- create or mutate reconciliation
- create or mutate payment settlement
- mark anything paid
- verify payment
- create entitlement
- issue an Activation Code

Authority flow:

    authenticated operator
        + manual_approval_request_id
        + registration_request_id
        -> authoritative registration/customer
        -> durable manual approval record
        -> CustomerSetupActivationService.activate()

The resulting Setup Activation continues through the existing
access-code issuance boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
from typing import Any


@dataclass(frozen=True)
class CustomerManualCommercialActivationRecord:
    manual_approval_request_id: str
    registration_request_id: str
    operator_id: str
    customer_id: str
    setup_activation_id: str

    def __post_init__(self) -> None:
        for name in (
            "manual_approval_request_id",
            "registration_request_id",
            "operator_id",
            "customer_id",
            "setup_activation_id",
        ):
            object.__setattr__(
                self,
                name,
                self._normalize_required_string(
                    getattr(self, name),
                    name=name,
                ),
            )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be str.")

        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{name} is required.")

        return normalized


@dataclass(frozen=True)
class CustomerManualCommercialActivationResult:
    manual_approval_request_id: str
    registration_request_id: str
    operator_id: str
    customer_id: str
    setup_activation_id: str

    def __post_init__(self) -> None:
        validated = CustomerManualCommercialActivationRecord(
            manual_approval_request_id=(
                self.manual_approval_request_id
            ),
            registration_request_id=(
                self.registration_request_id
            ),
            operator_id=self.operator_id,
            customer_id=self.customer_id,
            setup_activation_id=self.setup_activation_id,
        )

        for name in (
            "manual_approval_request_id",
            "registration_request_id",
            "operator_id",
            "customer_id",
            "setup_activation_id",
        ):
            object.__setattr__(
                self,
                name,
                getattr(validated, name),
            )


class CustomerManualCommercialActivationStore:
    """
    Durable authoritative owner of manual commercial approvals.

    One manual_approval_request_id is permanently bound to one
    registration, operator, customer, and Setup Activation.
    """

    _VERSION = 1

    def __init__(
        self,
        storage_path: Path,
    ) -> None:
        if not isinstance(storage_path, Path):
            raise TypeError("storage_path must be Path.")

        self.storage_path = storage_path
        self._records: dict[
            str,
            CustomerManualCommercialActivationRecord,
        ] = {}
        self._ready = False
        self._lock = threading.RLock()

    def is_ready(self) -> bool:
        return self._ready

    def open_or_initialize(self) -> None:
        """
        Open durable state if present; otherwise create the
        initial empty durable document.

        Bootstrap ownership deliberately lives here, not main.py.
        """

        with self._lock:
            if self._ready:
                return

            if self.storage_path.exists():
                if not self.storage_path.is_file():
                    raise RuntimeError(
                        "Manual commercial activation storage "
                        "path is not a file."
                    )

                self._restore_from_disk()
                self._ready = True
                return

            self.storage_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._persist_records({})
            self._records = {}
            self._ready = True

    def get(
        self,
        *,
        manual_approval_request_id: str,
    ) -> CustomerManualCommercialActivationRecord | None:
        self._require_ready()

        request_id = (
            CustomerManualCommercialActivationRecord
            ._normalize_required_string(
                manual_approval_request_id,
                name="manual_approval_request_id",
            )
        )

        with self._lock:
            return self._records.get(request_id)

    def register(
        self,
        record: CustomerManualCommercialActivationRecord,
    ) -> CustomerManualCommercialActivationRecord:
        if not isinstance(
            record,
            CustomerManualCommercialActivationRecord,
        ):
            raise TypeError(
                "CustomerManualCommercialActivationStore "
                "requires "
                "CustomerManualCommercialActivationRecord."
            )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                record.manual_approval_request_id
            )

            if existing is not None:
                if existing != record:
                    raise ValueError(
                        "Manual commercial approval request "
                        "is already bound to different facts."
                    )

                return existing

            next_records = dict(self._records)
            next_records[
                record.manual_approval_request_id
            ] = record

            # Durable state advances before RAM.
            self._persist_records(next_records)
            self._records = next_records

            return record

    def all(
        self,
    ) -> tuple[
        CustomerManualCommercialActivationRecord,
        ...,
    ]:
        self._require_ready()

        with self._lock:
            return tuple(
                self._records[key]
                for key in sorted(self._records)
            )

    def _restore_from_disk(self) -> None:
        try:
            raw = self.storage_path.read_text(
                encoding="utf-8"
            )
            payload = json.loads(raw)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as error:
            raise RuntimeError(
                "Manual commercial activation store "
                "could not be restored."
            ) from error

        if not isinstance(payload, dict):
            raise RuntimeError(
                "Manual commercial activation store "
                "payload is invalid."
            )

        if set(payload) != {
            "version",
            "records",
        }:
            raise RuntimeError(
                "Manual commercial activation store "
                "payload fields are invalid."
            )

        if payload["version"] != self._VERSION:
            raise RuntimeError(
                "Manual commercial activation store "
                "version is unsupported."
            )

        raw_records = payload["records"]

        if not isinstance(raw_records, list):
            raise RuntimeError(
                "Manual commercial activation records "
                "payload is invalid."
            )

        records: dict[
            str,
            CustomerManualCommercialActivationRecord,
        ] = {}

        for raw_record in raw_records:
            if (
                not isinstance(raw_record, dict)
                or set(raw_record)
                != {
                    "manual_approval_request_id",
                    "registration_request_id",
                    "operator_id",
                    "customer_id",
                    "setup_activation_id",
                }
            ):
                raise RuntimeError(
                    "Manual commercial activation record "
                    "payload is invalid."
                )

            try:
                record = (
                    CustomerManualCommercialActivationRecord(
                        manual_approval_request_id=raw_record[
                            "manual_approval_request_id"
                        ],
                        registration_request_id=raw_record[
                            "registration_request_id"
                        ],
                        operator_id=raw_record[
                            "operator_id"
                        ],
                        customer_id=raw_record[
                            "customer_id"
                        ],
                        setup_activation_id=raw_record[
                            "setup_activation_id"
                        ],
                    )
                )
            except (TypeError, ValueError) as error:
                raise RuntimeError(
                    "Manual commercial activation record "
                    "is invalid."
                ) from error

            if (
                record.manual_approval_request_id
                in records
            ):
                raise RuntimeError(
                    "Duplicate manual commercial approval "
                    "request identity."
                )

            records[
                record.manual_approval_request_id
            ] = record

        self._records = records

    def _persist_records(
        self,
        records: dict[
            str,
            CustomerManualCommercialActivationRecord,
        ],
    ) -> None:
        payload: dict[str, Any] = {
            "version": self._VERSION,
            "records": [
                {
                    "manual_approval_request_id": (
                        record.manual_approval_request_id
                    ),
                    "registration_request_id": (
                        record.registration_request_id
                    ),
                    "operator_id": record.operator_id,
                    "customer_id": record.customer_id,
                    "setup_activation_id": (
                        record.setup_activation_id
                    ),
                }
                for _, record in sorted(
                    records.items()
                )
            ],
        }

        serialized = json.dumps(
            payload,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self.storage_path.with_name(
            f".{self.storage_path.name}.tmp"
        )

        try:
            temporary_path.write_text(
                serialized + "\n",
                encoding="utf-8",
            )
            os.replace(
                temporary_path,
                self.storage_path,
            )
        except OSError:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise

    def _require_ready(self) -> None:
        if not self._ready:
            raise RuntimeError(
                "Manual commercial activation store "
                "is not initialized."
            )


class CustomerManualCommercialActivationService:
    """
    Converge authenticated manual approval into one authoritative
    Setup Activation without fabricating payment truth.
    """

    def __init__(
        self,
        *,
        approval_store: CustomerManualCommercialActivationStore,
        registration_service,
        setup_activation_service,
    ) -> None:
        if not isinstance(
            approval_store,
            CustomerManualCommercialActivationStore,
        ):
            raise TypeError(
                "approval_store must be "
                "CustomerManualCommercialActivationStore."
            )

        if not approval_store.is_ready():
            raise RuntimeError(
                "Manual commercial activation store "
                "is not initialized."
            )

        register_customer = getattr(
            registration_service,
            "register",
            None,
        )

        if not callable(register_customer):
            raise TypeError(
                "registration_service must expose register()."
            )

        activate_setup = getattr(
            setup_activation_service,
            "activate",
            None,
        )

        if not callable(activate_setup):
            raise TypeError(
                "setup_activation_service must expose activate()."
            )

        self._approval_store = approval_store
        self._register_customer = register_customer
        self._activate_setup = activate_setup
        self._lock = threading.RLock()

    def approve(
        self,
        *,
        manual_approval_request_id: str,
        registration_request_id: str,
        operator_id: str,
    ) -> CustomerManualCommercialActivationResult:
        normalized_request_id = (
            CustomerManualCommercialActivationRecord
            ._normalize_required_string(
                manual_approval_request_id,
                name="manual_approval_request_id",
            )
        )

        normalized_registration_request_id = (
            CustomerManualCommercialActivationRecord
            ._normalize_required_string(
                registration_request_id,
                name="registration_request_id",
            )
        )

        normalized_operator_id = (
            CustomerManualCommercialActivationRecord
            ._normalize_required_string(
                operator_id,
                name="operator_id",
            )
        )

        with self._lock:
            existing = self._approval_store.get(
                manual_approval_request_id=(
                    normalized_request_id
                )
            )

            if existing is not None:
                if (
                    existing.registration_request_id
                    != normalized_registration_request_id
                    or existing.operator_id
                    != normalized_operator_id
                ):
                    raise ValueError(
                        "Manual commercial approval request "
                        "is already bound to different facts."
                    )

                return self._build_result(existing)

            registration = self._register_customer(
                registration_request_id=(
                    normalized_registration_request_id
                )
            )

            authoritative_registration_request_id = getattr(
                registration,
                "registration_request_id",
                None,
            )
            customer_id = getattr(
                registration,
                "customer_id",
                None,
            )

            if (
                authoritative_registration_request_id
                != normalized_registration_request_id
            ):
                raise RuntimeError(
                    "Registration request identity did not "
                    "converge."
                )

            normalized_customer_id = (
                CustomerManualCommercialActivationRecord
                ._normalize_required_string(
                    customer_id,
                    name="customer_id",
                )
            )

            activation_request_id = (
                "manual-commercial-activation-"
                f"{normalized_request_id}"
            )

            activation = self._activate_setup(
                activation_request_id=(
                    activation_request_id
                ),
                customer_id=normalized_customer_id,
            )

            activation_customer_id = getattr(
                activation,
                "customer_id",
                None,
            )

            if (
                activation_customer_id
                != normalized_customer_id
            ):
                raise RuntimeError(
                    "Setup activation customer identity "
                    "did not converge."
                )

            setup_activation_id = (
                CustomerManualCommercialActivationRecord
                ._normalize_required_string(
                    getattr(
                        activation,
                        "setup_activation_id",
                        None,
                    ),
                    name="setup_activation_id",
                )
            )

            record = (
                CustomerManualCommercialActivationRecord(
                    manual_approval_request_id=(
                        normalized_request_id
                    ),
                    registration_request_id=(
                        normalized_registration_request_id
                    ),
                    operator_id=normalized_operator_id,
                    customer_id=normalized_customer_id,
                    setup_activation_id=(
                        setup_activation_id
                    ),
                )
            )

            stored = self._approval_store.register(
                record
            )

            return self._build_result(stored)

    @staticmethod
    def _build_result(
        record: CustomerManualCommercialActivationRecord,
    ) -> CustomerManualCommercialActivationResult:
        return CustomerManualCommercialActivationResult(
            manual_approval_request_id=(
                record.manual_approval_request_id
            ),
            registration_request_id=(
                record.registration_request_id
            ),
            operator_id=record.operator_id,
            customer_id=record.customer_id,
            setup_activation_id=(
                record.setup_activation_id
            ),
        )
