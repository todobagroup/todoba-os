from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
import os
from pathlib import Path
import threading
import uuid

from backend.commercial.customer_commercial_order_service import (
    CustomerCommercialOrderStatus,
    CustomerCommercialOrderStore,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentStatus,
    CustomerPaymentIntentStore,
    PaymentRail,
)


class CustomerVndBankReconciliationStatus(
    str,
    Enum,
):
    CONFIRMED = "CONFIRMED"


@dataclass(
    frozen=True,
)
class CustomerVndBankReconciliationRecord:
    """
    Durable server-side truth for one operator-confirmed
    VND bank transfer reconciliation.

    This record is not settlement and grants no activation
    authority.
    """

    reconciliation_request_id: str
    reconciliation_id: str
    payment_intent_id: str
    order_id: str
    customer_id: str
    bank_reference: str
    amount_minor: int
    currency: str
    operator_id: str
    status: CustomerVndBankReconciliationStatus

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "reconciliation_request_id",
            "reconciliation_id",
            "payment_intent_id",
            "order_id",
            "customer_id",
            "bank_reference",
            "operator_id",
        ):
            object.__setattr__(
                self,
                name,
                self._normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

        if (
            not isinstance(
                self.amount_minor,
                int,
            )
            or isinstance(
                self.amount_minor,
                bool,
            )
            or self.amount_minor <= 0
        ):
            raise ValueError(
                "amount_minor must be a positive integer."
            )

        normalized_currency = (
            self._normalize_required_string(
                self.currency,
                name="currency",
            ).upper()
        )

        if normalized_currency != "VND":
            raise ValueError(
                "VND bank reconciliation currency must be VND."
            )

        object.__setattr__(
            self,
            "currency",
            normalized_currency,
        )

        if not isinstance(
            self.status,
            CustomerVndBankReconciliationStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerVndBankReconciliationStatus."
            )

        if (
            self.status
            is not CustomerVndBankReconciliationStatus.CONFIRMED
        ):
            raise ValueError(
                "Unsupported VND bank reconciliation status."
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


class CustomerVndBankReconciliationStore:
    """
    Durable authoritative owner of confirmed VND bank
    reconciliation records.

    Primary identity:
        reconciliation_id

    Idempotency identity:
        reconciliation_request_id

    Replay identity:
        bank_reference
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
        self._records: dict[
            str,
            CustomerVndBankReconciliationRecord,
        ] = {}
        self._reconciliation_id_by_request_id: dict[
            str,
            str,
        ] = {}
        self._reconciliation_id_by_bank_reference: dict[
            str,
            str,
        ] = {}
        self._reconciliation_id_by_payment_intent_id: dict[
            str,
            str,
        ] = {}
        self._ready = False
        self._lock = threading.RLock()

    def initialize_empty(
        self,
    ) -> None:
        with self._lock:
            if self.storage_path.exists():
                raise RuntimeError(
                    "VND bank reconciliation store "
                    "already exists."
                )

            self.storage_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._records = {}
            self._reconciliation_id_by_request_id = {}
            self._reconciliation_id_by_bank_reference = {}
            self._reconciliation_id_by_payment_intent_id = {}
            self._persist()
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if not self.storage_path.exists():
                raise RuntimeError(
                    "VND bank reconciliation store "
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
                    "VND bank reconciliation store "
                    "could not be opened."
                ) from exc

            if not isinstance(
                payload,
                list,
            ):
                raise RuntimeError(
                    "VND bank reconciliation store "
                    "payload is invalid."
                )

            records: dict[
                str,
                CustomerVndBankReconciliationRecord,
            ] = {}
            request_index: dict[
                str,
                str,
            ] = {}
            reference_index: dict[
                str,
                str,
            ] = {}
            payment_intent_index: dict[
                str,
                str,
            ] = {}

            for raw in payload:
                if not isinstance(
                    raw,
                    dict,
                ):
                    raise RuntimeError(
                        "VND bank reconciliation record "
                        "payload is invalid."
                    )

                try:
                    record = (
                        CustomerVndBankReconciliationRecord(
                            reconciliation_request_id=(
                                raw[
                                    "reconciliation_request_id"
                                ]
                            ),
                            reconciliation_id=raw[
                                "reconciliation_id"
                            ],
                            payment_intent_id=raw[
                                "payment_intent_id"
                            ],
                            order_id=raw[
                                "order_id"
                            ],
                            customer_id=raw[
                                "customer_id"
                            ],
                            bank_reference=raw[
                                "bank_reference"
                            ],
                            amount_minor=raw[
                                "amount_minor"
                            ],
                            currency=raw[
                                "currency"
                            ],
                            operator_id=raw[
                                "operator_id"
                            ],
                            status=(
                                CustomerVndBankReconciliationStatus(
                                    raw["status"]
                                )
                            ),
                        )
                    )
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    raise RuntimeError(
                        "VND bank reconciliation record "
                        "payload is invalid."
                    ) from exc

                if record.reconciliation_id in records:
                    raise RuntimeError(
                        "Duplicate reconciliation_id."
                    )

                if (
                    record.reconciliation_request_id
                    in request_index
                ):
                    raise RuntimeError(
                        "Duplicate reconciliation_request_id."
                    )

                if (
                    record.bank_reference
                    in reference_index
                ):
                    raise RuntimeError(
                        "Duplicate bank_reference."
                    )

                if (
                    record.payment_intent_id
                    in payment_intent_index
                ):
                    raise RuntimeError(
                        "Duplicate payment_intent_id."
                    )

                records[
                    record.reconciliation_id
                ] = record
                request_index[
                    record.reconciliation_request_id
                ] = record.reconciliation_id
                reference_index[
                    record.bank_reference
                ] = record.reconciliation_id
                payment_intent_index[
                    record.payment_intent_id
                ] = record.reconciliation_id

            self._records = records
            self._reconciliation_id_by_request_id = (
                request_index
            )
            self._reconciliation_id_by_bank_reference = (
                reference_index
            )
            self._reconciliation_id_by_payment_intent_id = (
                payment_intent_index
            )
            self._ready = True

    def register(
        self,
        record: CustomerVndBankReconciliationRecord,
    ) -> CustomerVndBankReconciliationRecord:
        if not isinstance(
            record,
            CustomerVndBankReconciliationRecord,
        ):
            raise TypeError(
                "record must be "
                "CustomerVndBankReconciliationRecord."
            )

        with self._lock:
            self._require_ready()

            existing_request = (
                self.get_by_reconciliation_request_id(
                    reconciliation_request_id=(
                        record.reconciliation_request_id
                    )
                )
            )

            if existing_request is not None:
                if existing_request != record:
                    raise ValueError(
                        "Reconciliation request is already "
                        "bound to different facts."
                    )

                return existing_request

            existing_intent = (
                self.get_by_payment_intent_id(
                    payment_intent_id=(
                        record.payment_intent_id
                    )
                )
            )

            if existing_intent is not None:
                raise ValueError(
                    "Payment intent is already reconciled."
                )

            existing_reference = (
                self.get_by_bank_reference(
                    bank_reference=record.bank_reference
                )
            )

            if existing_reference is not None:
                raise ValueError(
                    "Bank reference is already reconciled."
                )

            if (
                record.reconciliation_id
                in self._records
            ):
                raise ValueError(
                    "reconciliation_id already exists."
                )

            self._records[
                record.reconciliation_id
            ] = record
            self._reconciliation_id_by_request_id[
                record.reconciliation_request_id
            ] = record.reconciliation_id
            self._reconciliation_id_by_bank_reference[
                record.bank_reference
            ] = record.reconciliation_id
            self._reconciliation_id_by_payment_intent_id[
                record.payment_intent_id
            ] = record.reconciliation_id

            try:
                self._persist()
            except Exception:
                del self._records[
                    record.reconciliation_id
                ]
                del self._reconciliation_id_by_request_id[
                    record.reconciliation_request_id
                ]
                del self._reconciliation_id_by_bank_reference[
                    record.bank_reference
                ]
                del self._reconciliation_id_by_payment_intent_id[
                    record.payment_intent_id
                ]
                raise

            return record

    def get(
        self,
        *,
        reconciliation_id: str,
    ) -> CustomerVndBankReconciliationRecord | None:
        with self._lock:
            self._require_ready()
            normalized = (
                CustomerVndBankReconciliationRecord
                ._normalize_required_string(
                    reconciliation_id,
                    name="reconciliation_id",
                )
            )
            return self._records.get(
                normalized
            )

    def get_by_reconciliation_request_id(
        self,
        *,
        reconciliation_request_id: str,
    ) -> CustomerVndBankReconciliationRecord | None:
        with self._lock:
            self._require_ready()

            normalized = (
                CustomerVndBankReconciliationRecord
                ._normalize_required_string(
                    reconciliation_request_id,
                    name="reconciliation_request_id",
                )
            )

            reconciliation_id = (
                self._reconciliation_id_by_request_id.get(
                    normalized
                )
            )

            if reconciliation_id is None:
                return None

            return self._records[
                reconciliation_id
            ]

    def get_by_payment_intent_id(
        self,
        *,
        payment_intent_id: str,
    ) -> CustomerVndBankReconciliationRecord | None:
        with self._lock:
            self._require_ready()

            normalized = (
                CustomerVndBankReconciliationRecord
                ._normalize_required_string(
                    payment_intent_id,
                    name="payment_intent_id",
                )
            )

            reconciliation_id = (
                self._reconciliation_id_by_payment_intent_id.get(
                    normalized
                )
            )

            if reconciliation_id is None:
                return None

            return self._records[
                reconciliation_id
            ]
    def get_by_bank_reference(
        self,
        *,
        bank_reference: str,
    ) -> CustomerVndBankReconciliationRecord | None:
        with self._lock:
            self._require_ready()

            normalized = (
                CustomerVndBankReconciliationRecord
                ._normalize_required_string(
                    bank_reference,
                    name="bank_reference",
                )
            )

            reconciliation_id = (
                self._reconciliation_id_by_bank_reference.get(
                    normalized
                )
            )

            if reconciliation_id is None:
                return None

            return self._records[
                reconciliation_id
            ]

    def size(
        self,
    ) -> int:
        with self._lock:
            self._require_ready()
            return len(
                self._records
            )

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def _persist(
        self,
    ) -> None:
        payload = []

        for record in self._records.values():
            raw = asdict(
                record
            )
            raw["status"] = record.status.value
            payload.append(
                raw
            )

        serialized = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )

        temporary_path = self.storage_path.with_name(
            f".{self.storage_path.name}.{uuid.uuid4().hex}.tmp"
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
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "VND bank reconciliation store "
                "is not initialized."
            )


class CustomerVndBankReconciliationService:
    """
    Server/admin-only authority for confirming one observed
    VND bank transfer against TODOBA's authoritative payment
    intent and commercial order.

    This service does not receive customer proof, create payment
    evidence, settle payment, or activate Setup.
    """

    def __init__(
        self,
        *,
        reconciliation_store: CustomerVndBankReconciliationStore,
        payment_intent_store: CustomerPaymentIntentStore,
        order_store: CustomerCommercialOrderStore,
    ) -> None:
        if not isinstance(
            reconciliation_store,
            CustomerVndBankReconciliationStore,
        ):
            raise TypeError(
                "reconciliation_store must be "
                "CustomerVndBankReconciliationStore."
            )

        if not isinstance(
            payment_intent_store,
            CustomerPaymentIntentStore,
        ):
            raise TypeError(
                "payment_intent_store must be "
                "CustomerPaymentIntentStore."
            )

        if not isinstance(
            order_store,
            CustomerCommercialOrderStore,
        ):
            raise TypeError(
                "order_store must be "
                "CustomerCommercialOrderStore."
            )

        self._reconciliation_store = (
            reconciliation_store
        )
        self._payment_intent_store = (
            payment_intent_store
        )
        self._order_store = order_store
        self._lock = threading.RLock()

    def confirm(
        self,
        *,
        reconciliation_request_id: str,
        payment_intent_id: str,
        bank_reference: str,
        amount_minor: int,
        currency: str,
        operator_id: str,
    ) -> CustomerVndBankReconciliationRecord:
        normalized_request_id = (
            CustomerVndBankReconciliationRecord
            ._normalize_required_string(
                reconciliation_request_id,
                name="reconciliation_request_id",
            )
        )
        normalized_intent_id = (
            CustomerVndBankReconciliationRecord
            ._normalize_required_string(
                payment_intent_id,
                name="payment_intent_id",
            )
        )
        normalized_bank_reference = (
            CustomerVndBankReconciliationRecord
            ._normalize_required_string(
                bank_reference,
                name="bank_reference",
            )
        )
        normalized_operator_id = (
            CustomerVndBankReconciliationRecord
            ._normalize_required_string(
                operator_id,
                name="operator_id",
            )
        )

        if (
            not isinstance(
                amount_minor,
                int,
            )
            or isinstance(
                amount_minor,
                bool,
            )
            or amount_minor <= 0
        ):
            raise ValueError(
                "amount_minor must be a positive integer."
            )

        normalized_currency = (
            CustomerVndBankReconciliationRecord
            ._normalize_required_string(
                currency,
                name="currency",
            ).upper()
        )

        if normalized_currency != "VND":
            raise ValueError(
                "VND bank reconciliation currency must be VND."
            )

        with self._lock:
            self._require_sources_ready()

            intent = self._payment_intent_store.get(
                payment_intent_id=normalized_intent_id
            )

            if intent is None:
                raise ValueError(
                    "Payment intent is not authoritative."
                )

            if (
                intent.payment_intent_id
                != normalized_intent_id
                or intent.payment_rail
                is not PaymentRail.VND_BANK_TRANSFER
                or intent.status
                is not CustomerPaymentIntentStatus.PENDING
            ):
                raise ValueError(
                    "Payment intent is not eligible for "
                    "VND bank reconciliation."
                )

            order = self._order_store.get(
                order_id=intent.order_id
            )

            if order is None:
                raise ValueError(
                    "Commercial order is not authoritative."
                )

            if (
                order.order_id != intent.order_id
                or order.status
                is not CustomerCommercialOrderStatus.PENDING
            ):
                raise ValueError(
                    "Commercial order is not eligible for "
                    "VND bank reconciliation."
                )

            if (
                order.amount_minor != amount_minor
                or order.currency != normalized_currency
            ):
                raise ValueError(
                    "Bank reconciliation amount or currency "
                    "does not match authoritative order."
                )

            existing_request = (
                self._reconciliation_store
                .get_by_reconciliation_request_id(
                    reconciliation_request_id=(
                        normalized_request_id
                    )
                )
            )

            if existing_request is not None:
                if not self._matches_request(
                    record=existing_request,
                    payment_intent_id=normalized_intent_id,
                    order_id=order.order_id,
                    customer_id=order.customer_id,
                    bank_reference=normalized_bank_reference,
                    amount_minor=amount_minor,
                    currency=normalized_currency,
                    operator_id=normalized_operator_id,
                ):
                    raise ValueError(
                        "Reconciliation request is already "
                        "bound to different facts."
                    )

                return existing_request

            existing_reference = (
                self._reconciliation_store
                .get_by_bank_reference(
                    bank_reference=(
                        normalized_bank_reference
                    )
                )
            )

            if existing_reference is not None:
                raise ValueError(
                    "Bank reference is already reconciled."
                )

            record = CustomerVndBankReconciliationRecord(
                reconciliation_request_id=(
                    normalized_request_id
                ),
                reconciliation_id=(
                    "vnd-bank-reconciliation-"
                    f"{uuid.uuid4().hex}"
                ),
                payment_intent_id=normalized_intent_id,
                order_id=order.order_id,
                customer_id=order.customer_id,
                bank_reference=normalized_bank_reference,
                amount_minor=amount_minor,
                currency=normalized_currency,
                operator_id=normalized_operator_id,
                status=(
                    CustomerVndBankReconciliationStatus.CONFIRMED
                ),
            )

            return self._reconciliation_store.register(
                record
            )

    @staticmethod
    def _matches_request(
        *,
        record: CustomerVndBankReconciliationRecord,
        payment_intent_id: str,
        order_id: str,
        customer_id: str,
        bank_reference: str,
        amount_minor: int,
        currency: str,
        operator_id: str,
    ) -> bool:
        return (
            record.payment_intent_id == payment_intent_id
            and record.order_id == order_id
            and record.customer_id == customer_id
            and record.bank_reference == bank_reference
            and record.amount_minor == amount_minor
            and record.currency == currency
            and record.operator_id == operator_id
            and record.status
            is CustomerVndBankReconciliationStatus.CONFIRMED
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._reconciliation_store.is_ready():
            raise RuntimeError(
                "VND bank reconciliation store "
                "is not initialized."
            )

        if not self._payment_intent_store.is_ready():
            raise RuntimeError(
                "Payment intent store is not initialized."
            )

        if not self._order_store.is_ready():
            raise RuntimeError(
                "Commercial order store is not initialized."
            )
