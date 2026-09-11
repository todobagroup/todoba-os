"""
TODOBA Customer Payment Settlement Service

Owns durable server-side payment settlement truth.

Trust boundary:

    PaymentVerificationAssertion
        -> authoritative Payment Evidence
        -> authoritative Payment Intent
        -> authoritative Commercial Order
        -> generated settlement_id
        -> SETTLED

Security rules:
- verification assertion is server-side typed input
- assertion must match authoritative evidence exactly
- evidence must match authoritative payment intent exactly
- payment intent must match authoritative commercial order exactly
- verified customer, amount, and currency must match order truth
- verification assertion identity is immutable
- one evidence can create at most one settlement
- one commercial order can create at most one settlement
- durable settlement is written before RAM advances

This owner deliberately does not:
- call PayPal or bank APIs
- verify webhook signatures itself
- accept client payment proof
- process raw provider callbacks
- grant setup activation
- issue activation/access codes
- provision customer setup
- mutate deployment entitlement
- expose an HTTP API
"""

from __future__ import annotations

from dataclasses import dataclass
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
from backend.commercial.customer_payment_evidence_service import (
    CustomerPaymentEvidenceStatus,
    CustomerPaymentEvidenceStore,
    PaymentEvidenceSource,
)
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentStatus,
    CustomerPaymentIntentStore,
    PaymentRail,
)


STORE_VERSION = 1
_ID_GENERATION_ATTEMPTS = 128


class CustomerPaymentSettlementStatus(
    str,
    Enum,
):
    SETTLED = "SETTLED"


@dataclass(
    frozen=True,
)
class PaymentVerificationAssertion:
    """
    Normalized server-side verification result.

    Provider-specific adapters are responsible for creating this
    assertion only after performing their own authenticity checks.
    This object itself is not proof and carries no provider secret.
    """

    verification_assertion_id: str
    payment_evidence_id: str
    payment_intent_id: str
    order_id: str
    customer_id: str
    amount_minor: int
    currency: str
    evidence_source: PaymentEvidenceSource
    external_evidence_id: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "verification_assertion_id",
            "payment_evidence_id",
            "payment_intent_id",
            "order_id",
            "customer_id",
            "external_evidence_id",
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

        object.__setattr__(
            self,
            "amount_minor",
            self._normalize_amount_minor(
                self.amount_minor
            ),
        )

        object.__setattr__(
            self,
            "currency",
            self._normalize_currency(
                self.currency
            ),
        )

        if not isinstance(
            self.evidence_source,
            PaymentEvidenceSource,
        ):
            raise TypeError(
                "evidence_source must be "
                "PaymentEvidenceSource."
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

    @staticmethod
    def _normalize_amount_minor(
        value: int,
    ) -> int:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
        ):
            raise TypeError(
                "amount_minor must be int."
            )

        if value <= 0:
            raise ValueError(
                "amount_minor must be positive."
            )

        return value

    @staticmethod
    def _normalize_currency(
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "currency must be str."
            )

        normalized = value.strip().upper()

        if (
            len(normalized) != 3
            or not normalized.isascii()
            or not normalized.isalpha()
        ):
            raise ValueError(
                "currency must be a three-letter "
                "ASCII currency code."
            )

        return normalized


@dataclass(
    frozen=True,
)
class CustomerPaymentSettlementRecord:
    """
    Immutable authoritative settlement snapshot.
    """

    verification_assertion_id: str
    settlement_id: str
    payment_evidence_id: str
    payment_intent_id: str
    order_id: str
    customer_id: str
    amount_minor: int
    currency: str
    status: CustomerPaymentSettlementStatus

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "verification_assertion_id",
            "settlement_id",
            "payment_evidence_id",
            "payment_intent_id",
            "order_id",
            "customer_id",
        ):
            object.__setattr__(
                self,
                name,
                PaymentVerificationAssertion
                ._normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

        object.__setattr__(
            self,
            "amount_minor",
            PaymentVerificationAssertion
            ._normalize_amount_minor(
                self.amount_minor
            ),
        )

        object.__setattr__(
            self,
            "currency",
            PaymentVerificationAssertion
            ._normalize_currency(
                self.currency
            ),
        )

        if not isinstance(
            self.status,
            CustomerPaymentSettlementStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerPaymentSettlementStatus."
            )

        if (
            self.status
            is not CustomerPaymentSettlementStatus.SETTLED
        ):
            raise ValueError(
                "Unsupported customer payment "
                "settlement status."
            )


class CustomerPaymentSettlementStore:
    """
    Durable authoritative settlement registry.

    Primary identity:
        settlement_id

    Idempotency identity:
        verification_assertion_id

    Security uniqueness:
        payment_evidence_id
        order_id
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
            CustomerPaymentSettlementRecord,
        ] = {}

        self._settlement_id_by_assertion_id: dict[
            str,
            str,
        ] = {}

        self._settlement_id_by_evidence_id: dict[
            str,
            str,
        ] = {}

        self._settlement_id_by_order_id: dict[
            str,
            str,
        ] = {}

        self._ready = False
        self._lock = threading.RLock()

        if self.storage_path.exists():
            self._restore_from_disk()

    def initialize_empty(
        self,
    ) -> None:
        with self._lock:
            if self._ready:
                return

            if self.storage_path.exists():
                self._restore_from_disk()
                return

            self._write_records(
                {}
            )

            self._records = {}
            self._settlement_id_by_assertion_id = {}
            self._settlement_id_by_evidence_id = {}
            self._settlement_id_by_order_id = {}
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        record: CustomerPaymentSettlementRecord,
    ) -> CustomerPaymentSettlementRecord:
        if not isinstance(
            record,
            CustomerPaymentSettlementRecord,
        ):
            raise TypeError(
                "CustomerPaymentSettlementStore requires "
                "CustomerPaymentSettlementRecord."
            )

        with self._lock:
            self._require_ready()

            existing_id = (
                self._settlement_id_by_assertion_id.get(
                    record.verification_assertion_id
                )
            )

            if existing_id is not None:
                existing = self._records[
                    existing_id
                ]

                if existing != record:
                    raise ValueError(
                        "Payment verification assertion "
                        "is already bound to different "
                        "settlement facts."
                    )

                return existing

            evidence_settlement_id = (
                self._settlement_id_by_evidence_id.get(
                    record.payment_evidence_id
                )
            )

            if evidence_settlement_id is not None:
                return self._records[
                    evidence_settlement_id
                ]

            order_settlement_id = (
                self._settlement_id_by_order_id.get(
                    record.order_id
                )
            )

            if order_settlement_id is not None:
                return self._records[
                    order_settlement_id
                ]

            existing = self._records.get(
                record.settlement_id
            )

            if existing is not None:
                if existing != record:
                    raise ValueError(
                        "Customer payment settlement ID "
                        "already exists."
                    )

                return existing

            candidate = dict(
                self._records
            )
            candidate[
                record.settlement_id
            ] = record

            self._write_records(
                candidate
            )

            assertion_index = dict(
                self._settlement_id_by_assertion_id
            )
            assertion_index[
                record.verification_assertion_id
            ] = record.settlement_id

            evidence_index = dict(
                self._settlement_id_by_evidence_id
            )
            evidence_index[
                record.payment_evidence_id
            ] = record.settlement_id

            order_index = dict(
                self._settlement_id_by_order_id
            )
            order_index[
                record.order_id
            ] = record.settlement_id

            self._records = candidate
            self._settlement_id_by_assertion_id = (
                assertion_index
            )
            self._settlement_id_by_evidence_id = (
                evidence_index
            )
            self._settlement_id_by_order_id = (
                order_index
            )

            return record

    def get(
        self,
        *,
        settlement_id: str,
    ) -> CustomerPaymentSettlementRecord | None:
        self._require_ready()

        normalized = (
            PaymentVerificationAssertion
            ._normalize_required_string(
                settlement_id,
                name="settlement_id",
            )
        )

        return self._records.get(
            normalized
        )

    def get_by_verification_assertion_id(
        self,
        *,
        verification_assertion_id: str,
    ) -> CustomerPaymentSettlementRecord | None:
        self._require_ready()

        normalized = (
            PaymentVerificationAssertion
            ._normalize_required_string(
                verification_assertion_id,
                name="verification_assertion_id",
            )
        )

        settlement_id = (
            self._settlement_id_by_assertion_id.get(
                normalized
            )
        )

        if settlement_id is None:
            return None

        return self._records[
            settlement_id
        ]

    def get_by_payment_evidence_id(
        self,
        *,
        payment_evidence_id: str,
    ) -> CustomerPaymentSettlementRecord | None:
        self._require_ready()

        normalized = (
            PaymentVerificationAssertion
            ._normalize_required_string(
                payment_evidence_id,
                name="payment_evidence_id",
            )
        )

        settlement_id = (
            self._settlement_id_by_evidence_id.get(
                normalized
            )
        )

        if settlement_id is None:
            return None

        return self._records[
            settlement_id
        ]

    def get_by_order_id(
        self,
        *,
        order_id: str,
    ) -> CustomerPaymentSettlementRecord | None:
        self._require_ready()

        normalized = (
            PaymentVerificationAssertion
            ._normalize_required_string(
                order_id,
                name="order_id",
            )
        )

        settlement_id = (
            self._settlement_id_by_order_id.get(
                normalized
            )
        )

        if settlement_id is None:
            return None

        return self._records[
            settlement_id
        ]

    def all(
        self,
    ) -> tuple[
        CustomerPaymentSettlementRecord,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._records[
                settlement_id
            ]
            for settlement_id in sorted(
                self._records
            )
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
                "Customer payment settlement store "
                "is not initialized."
            )

    def _restore_from_disk(
        self,
    ) -> None:
        try:
            payload = json.loads(
                self.storage_path.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "Customer payment settlement store "
                "is unreadable."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer payment settlement store "
                "must contain an object."
            )

        if set(
            payload
        ) != {
            "version",
            "records",
        }:
            raise ValueError(
                "Customer payment settlement store "
                "has invalid fields."
            )

        if (
            payload["version"]
            != STORE_VERSION
        ):
            raise ValueError(
                "Unsupported customer payment "
                "settlement store version."
            )

        items = payload[
            "records"
        ]

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer payment settlement records "
                "must be a list."
            )

        restored: dict[
            str,
            CustomerPaymentSettlementRecord,
        ] = {}

        assertion_index: dict[
            str,
            str,
        ] = {}

        evidence_index: dict[
            str,
            str,
        ] = {}

        order_index: dict[
            str,
            str,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer payment settlement item "
                    "must be an object."
                )

            if set(
                item
            ) != {
                "verification_assertion_id",
                "settlement_id",
                "payment_evidence_id",
                "payment_intent_id",
                "order_id",
                "customer_id",
                "amount_minor",
                "currency",
                "status",
            }:
                raise ValueError(
                    "Customer payment settlement item "
                    "has invalid fields."
                )

            try:
                record = CustomerPaymentSettlementRecord(
                    verification_assertion_id=item[
                        "verification_assertion_id"
                    ],
                    settlement_id=item[
                        "settlement_id"
                    ],
                    payment_evidence_id=item[
                        "payment_evidence_id"
                    ],
                    payment_intent_id=item[
                        "payment_intent_id"
                    ],
                    order_id=item[
                        "order_id"
                    ],
                    customer_id=item[
                        "customer_id"
                    ],
                    amount_minor=item[
                        "amount_minor"
                    ],
                    currency=item[
                        "currency"
                    ],
                    status=(
                        CustomerPaymentSettlementStatus(
                            item[
                                "status"
                            ]
                        )
                    ),
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Customer payment settlement item "
                    "is invalid."
                ) from exc

            if record.settlement_id in restored:
                raise ValueError(
                    "Duplicate customer payment "
                    "settlement ID."
                )

            if (
                record.verification_assertion_id
                in assertion_index
            ):
                raise ValueError(
                    "Duplicate payment verification "
                    "assertion."
                )

            if (
                record.payment_evidence_id
                in evidence_index
            ):
                raise ValueError(
                    "Duplicate settlement payment "
                    "evidence."
                )

            if (
                record.order_id
                in order_index
            ):
                raise ValueError(
                    "Duplicate settlement commercial "
                    "order."
                )

            restored[
                record.settlement_id
            ] = record

            assertion_index[
                record.verification_assertion_id
            ] = record.settlement_id

            evidence_index[
                record.payment_evidence_id
            ] = record.settlement_id

            order_index[
                record.order_id
            ] = record.settlement_id

        self._records = restored
        self._settlement_id_by_assertion_id = (
            assertion_index
        )
        self._settlement_id_by_evidence_id = (
            evidence_index
        )
        self._settlement_id_by_order_id = (
            order_index
        )
        self._ready = True

    def _write_records(
        self,
        records: dict[
            str,
            CustomerPaymentSettlementRecord,
        ],
    ) -> None:
        items = []

        for settlement_id in sorted(
            records
        ):
            record = records[
                settlement_id
            ]

            items.append(
                {
                    "verification_assertion_id": (
                        record.verification_assertion_id
                    ),
                    "settlement_id": (
                        record.settlement_id
                    ),
                    "payment_evidence_id": (
                        record.payment_evidence_id
                    ),
                    "payment_intent_id": (
                        record.payment_intent_id
                    ),
                    "order_id": (
                        record.order_id
                    ),
                    "customer_id": (
                        record.customer_id
                    ),
                    "amount_minor": (
                        record.amount_minor
                    ),
                    "currency": (
                        record.currency
                    ),
                    "status": (
                        record.status.value
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
                f".{self.storage_path.name}."
                f"{uuid.uuid4().hex}.tmp"
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


class CustomerPaymentSettlementService:
    """
    Convert one exact verified commercial chain into settlement truth.
    """

    def __init__(
        self,
        *,
        settlement_store: CustomerPaymentSettlementStore,
        payment_evidence_store: CustomerPaymentEvidenceStore,
        payment_intent_store: CustomerPaymentIntentStore,
        order_store: CustomerCommercialOrderStore,
    ) -> None:
        if not isinstance(
            settlement_store,
            CustomerPaymentSettlementStore,
        ):
            raise TypeError(
                "settlement_store must be "
                "CustomerPaymentSettlementStore."
            )

        if not isinstance(
            payment_evidence_store,
            CustomerPaymentEvidenceStore,
        ):
            raise TypeError(
                "payment_evidence_store must be "
                "CustomerPaymentEvidenceStore."
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

        for ready, name in (
            (
                settlement_store.is_ready(),
                "Customer payment settlement store",
            ),
            (
                payment_evidence_store.is_ready(),
                "Customer payment evidence store",
            ),
            (
                payment_intent_store.is_ready(),
                "Customer payment intent store",
            ),
            (
                order_store.is_ready(),
                "Customer commercial order store",
            ),
        ):
            if not ready:
                raise RuntimeError(
                    f"{name} is not initialized."
                )

        self._settlement_store = settlement_store
        self._payment_evidence_store = (
            payment_evidence_store
        )
        self._payment_intent_store = (
            payment_intent_store
        )
        self._order_store = order_store
        self._lock = threading.RLock()

    def settle(
        self,
        *,
        verification_assertion: PaymentVerificationAssertion,
    ) -> CustomerPaymentSettlementRecord:
        if not isinstance(
            verification_assertion,
            PaymentVerificationAssertion,
        ):
            raise TypeError(
                "verification_assertion must be "
                "PaymentVerificationAssertion."
            )

        with self._lock:
            self._require_sources_ready()

            existing_assertion = (
                self._settlement_store
                .get_by_verification_assertion_id(
                    verification_assertion_id=(
                        verification_assertion
                        .verification_assertion_id
                    )
                )
            )

            if existing_assertion is not None:
                if not self._settlement_matches_assertion(
                    settlement=existing_assertion,
                    assertion=verification_assertion,
                ):
                    raise ValueError(
                        "Payment verification assertion "
                        "is already bound to different "
                        "settlement facts."
                    )

                return existing_assertion

            (
                evidence,
                intent,
                order,
            ) = self._verify_authoritative_chain(
                verification_assertion
            )

            existing_evidence = (
                self._settlement_store
                .get_by_payment_evidence_id(
                    payment_evidence_id=(
                        evidence.payment_evidence_id
                    )
                )
            )

            if existing_evidence is not None:
                return existing_evidence

            existing_order = (
                self._settlement_store
                .get_by_order_id(
                    order_id=order.order_id
                )
            )

            if existing_order is not None:
                return existing_order

            record = self._create_settlement_record(
                verification_assertion=(
                    verification_assertion
                ),
                payment_evidence_id=(
                    evidence.payment_evidence_id
                ),
                payment_intent_id=(
                    intent.payment_intent_id
                ),
                order_id=order.order_id,
                customer_id=order.customer_id,
                amount_minor=order.amount_minor,
                currency=order.currency,
            )

            return self._settlement_store.register(
                record
            )

    def get(
        self,
        *,
        settlement_id: str,
    ) -> CustomerPaymentSettlementRecord | None:
        self._require_sources_ready()

        return self._settlement_store.get(
            settlement_id=settlement_id
        )

    def _verify_authoritative_chain(
        self,
        assertion: PaymentVerificationAssertion,
    ):
        evidence = self._payment_evidence_store.get(
            payment_evidence_id=(
                assertion.payment_evidence_id
            )
        )

        if evidence is None:
            raise ValueError(
                "Payment verification evidence "
                "is not authoritative."
            )

        if (
            evidence.payment_evidence_id
            != assertion.payment_evidence_id
            or evidence.payment_intent_id
            != assertion.payment_intent_id
            or evidence.evidence_source
            is not assertion.evidence_source
            or evidence.external_evidence_id
            != assertion.external_evidence_id
            or evidence.status
            is not CustomerPaymentEvidenceStatus.RECEIVED
        ):
            raise ValueError(
                "Payment verification evidence "
                "does not match authoritative truth."
            )

        intent = self._payment_intent_store.get(
            payment_intent_id=(
                assertion.payment_intent_id
            )
        )

        if intent is None:
            raise ValueError(
                "Payment verification intent "
                "is not authoritative."
            )

        if (
            intent.payment_intent_id
            != evidence.payment_intent_id
            or intent.order_id
            != assertion.order_id
            or intent.status
            is not CustomerPaymentIntentStatus.PENDING
        ):
            raise ValueError(
                "Payment verification intent "
                "does not match authoritative truth."
            )

        expected_source = self._source_for_rail(
            intent.payment_rail
        )

        if (
            assertion.evidence_source
            is not expected_source
        ):
            raise ValueError(
                "Payment verification evidence source "
                "does not match payment rail."
            )

        order = self._order_store.get(
            order_id=assertion.order_id
        )

        if order is None:
            raise ValueError(
                "Payment verification order "
                "is not authoritative."
            )

        if (
            order.order_id
            != intent.order_id
            or order.customer_id
            != assertion.customer_id
            or order.amount_minor
            != assertion.amount_minor
            or order.currency
            != assertion.currency
            or order.status
            is not CustomerCommercialOrderStatus.PENDING
        ):
            raise ValueError(
                "Payment verification commercial facts "
                "do not match authoritative order."
            )

        return (
            evidence,
            intent,
            order,
        )

    def _create_settlement_record(
        self,
        *,
        verification_assertion: PaymentVerificationAssertion,
        payment_evidence_id: str,
        payment_intent_id: str,
        order_id: str,
        customer_id: str,
        amount_minor: int,
        currency: str,
    ) -> CustomerPaymentSettlementRecord:
        for _ in range(
            _ID_GENERATION_ATTEMPTS
        ):
            settlement_id = (
                f"payment-settlement-{uuid.uuid4().hex}"
            )

            if (
                self._settlement_store.get(
                    settlement_id=settlement_id
                )
                is not None
            ):
                continue

            return CustomerPaymentSettlementRecord(
                verification_assertion_id=(
                    verification_assertion
                    .verification_assertion_id
                ),
                settlement_id=settlement_id,
                payment_evidence_id=payment_evidence_id,
                payment_intent_id=payment_intent_id,
                order_id=order_id,
                customer_id=customer_id,
                amount_minor=amount_minor,
                currency=currency,
                status=(
                    CustomerPaymentSettlementStatus.SETTLED
                ),
            )

        raise RuntimeError(
            "Unable to generate unique customer "
            "payment settlement identity."
        )

    @staticmethod
    def _settlement_matches_assertion(
        *,
        settlement: CustomerPaymentSettlementRecord,
        assertion: PaymentVerificationAssertion,
    ) -> bool:
        return (
            settlement.verification_assertion_id
            == assertion.verification_assertion_id
            and settlement.payment_evidence_id
            == assertion.payment_evidence_id
            and settlement.payment_intent_id
            == assertion.payment_intent_id
            and settlement.order_id
            == assertion.order_id
            and settlement.customer_id
            == assertion.customer_id
            and settlement.amount_minor
            == assertion.amount_minor
            and settlement.currency
            == assertion.currency
        )

    @staticmethod
    def _source_for_rail(
        payment_rail: PaymentRail,
    ) -> PaymentEvidenceSource:
        if payment_rail is PaymentRail.PAYPAL:
            return PaymentEvidenceSource.PAYPAL

        if (
            payment_rail
            is PaymentRail.VND_BANK_TRANSFER
        ):
            return (
                PaymentEvidenceSource
                .VND_BANK_TRANSFER
            )

        raise ValueError(
            "Payment verification encountered "
            "unsupported payment rail."
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._settlement_store.is_ready():
            raise RuntimeError(
                "Customer payment settlement store "
                "is not initialized."
            )

        if not self._payment_evidence_store.is_ready():
            raise RuntimeError(
                "Customer payment evidence store "
                "is not initialized."
            )

        if not self._payment_intent_store.is_ready():
            raise RuntimeError(
                "Customer payment intent store "
                "is not initialized."
            )

        if not self._order_store.is_ready():
            raise RuntimeError(
                "Customer commercial order store "
                "is not initialized."
            )
