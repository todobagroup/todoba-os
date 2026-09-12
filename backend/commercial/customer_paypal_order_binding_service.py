"""
TODOBA Customer PayPal Order Binding Service

Owns durable binding between one authoritative TODOBA PAYPAL
payment intent and one PayPal-created order identity.

Trust boundary:

    authoritative PAYPAL PaymentIntent
        -> authoritative CommercialOrder
        -> normalized PayPalOrderCreationResult
        -> durable PayPal order binding
        -> BOUND

Security rules:
- payment intent must exist exactly in CustomerPaymentIntentStore
- intent rail must be PAYPAL
- intent order must exist exactly in CustomerCommercialOrderStore
- PayPal request ID must equal payment_intent_id
- PayPal custom_id must equal payment_intent_id
- PayPal amount/currency must exactly match TODOBA order truth
- unsupported PayPal payment currency fails closed
- one payment intent can bind only one PayPal order
- one PayPal order can bind only one payment intent
- durable state is written before RAM advances

This owner deliberately does not:
- perform HTTP requests
- obtain OAuth tokens
- store PayPal client credentials
- verify webhooks
- receive payment evidence
- verify captures
- mark payment paid or settled
- grant setup activation
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
from backend.commercial.customer_payment_intent_service import (
    CustomerPaymentIntentResult,
    CustomerPaymentIntentStatus,
    CustomerPaymentIntentStore,
    PaymentRail,
)


STORE_VERSION = 1
_ID_GENERATION_ATTEMPTS = 128

_PAYPAL_PAYMENT_CURRENCIES = frozenset(
    {
        "AUD",
        "BRL",
        "CAD",
        "CNY",
        "CZK",
        "DKK",
        "EUR",
        "HKD",
        "HUF",
        "ILS",
        "JPY",
        "MYR",
        "MXN",
        "TWD",
        "NZD",
        "NOK",
        "PHP",
        "PLN",
        "GBP",
        "RUB",
        "SGD",
        "SEK",
        "CHF",
        "THB",
        "USD",
    }
)


class CustomerPayPalOrderBindingStatus(
    str,
    Enum,
):
    BOUND = "BOUND"


@dataclass(
    frozen=True,
)
class PayPalOrderCreationResult:
    """
    Normalized non-secret result from a PayPal create-order call.

    Network transport and credentials belong to a separate owner.
    """

    paypal_order_id: str
    paypal_request_id: str
    custom_id: str
    amount_minor: int
    currency: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "paypal_order_id",
            "paypal_request_id",
            "custom_id",
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
class CustomerPayPalOrderBindingRecord:
    """
    Immutable durable PayPal order binding.
    """

    paypal_binding_id: str
    paypal_order_id: str
    paypal_request_id: str
    payment_intent_id: str
    order_id: str
    amount_minor: int
    currency: str
    status: CustomerPayPalOrderBindingStatus

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "paypal_binding_id",
            "paypal_order_id",
            "paypal_request_id",
            "payment_intent_id",
            "order_id",
        ):
            object.__setattr__(
                self,
                name,
                PayPalOrderCreationResult
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
            PayPalOrderCreationResult
            ._normalize_amount_minor(
                self.amount_minor
            ),
        )

        object.__setattr__(
            self,
            "currency",
            PayPalOrderCreationResult
            ._normalize_currency(
                self.currency
            ),
        )

        if (
            self.currency
            not in _PAYPAL_PAYMENT_CURRENCIES
        ):
            raise ValueError(
                "currency is not supported "
                "for PayPal payments."
            )

        if (
            self.paypal_request_id
            != self.payment_intent_id
        ):
            raise ValueError(
                "paypal_request_id must equal "
                "payment_intent_id."
            )

        if not isinstance(
            self.status,
            CustomerPayPalOrderBindingStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerPayPalOrderBindingStatus."
            )

        if (
            self.status
            is not CustomerPayPalOrderBindingStatus.BOUND
        ):
            raise ValueError(
                "Unsupported customer PayPal order "
                "binding status."
            )


class CustomerPayPalOrderBindingStore:
    """
    Durable authoritative owner of PayPal order bindings.

    Primary identity:
        paypal_binding_id

    Internal uniqueness:
        payment_intent_id

    Provider uniqueness:
        paypal_order_id
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
            CustomerPayPalOrderBindingRecord,
        ] = {}

        self._binding_id_by_intent_id: dict[
            str,
            str,
        ] = {}

        self._binding_id_by_paypal_order_id: dict[
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
            self._binding_id_by_intent_id = {}
            self._binding_id_by_paypal_order_id = {}
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if not self.storage_path.exists():
                raise RuntimeError(
                    "Customer PayPal order binding store "
                    "does not exist."
                )

            if self._ready:
                return

            self._restore_from_disk()

    def is_ready(
        self,
    ) -> bool:
        return self._ready

    def register(
        self,
        record: CustomerPayPalOrderBindingRecord,
    ) -> CustomerPayPalOrderBindingRecord:
        if not isinstance(
            record,
            CustomerPayPalOrderBindingRecord,
        ):
            raise TypeError(
                "CustomerPayPalOrderBindingStore requires "
                "CustomerPayPalOrderBindingRecord."
            )

        with self._lock:
            self._require_ready()

            existing_intent_id = (
                self._binding_id_by_intent_id.get(
                    record.payment_intent_id
                )
            )

            if existing_intent_id is not None:
                existing = self._records[
                    existing_intent_id
                ]

                if existing != record:
                    raise ValueError(
                        "Payment intent is already bound "
                        "to another PayPal order."
                    )

                return existing

            existing_paypal_id = (
                self._binding_id_by_paypal_order_id.get(
                    record.paypal_order_id
                )
            )

            if existing_paypal_id is not None:
                existing = self._records[
                    existing_paypal_id
                ]

                if (
                    existing.payment_intent_id
                    != record.payment_intent_id
                ):
                    raise ValueError(
                        "PayPal order is already bound "
                        "to another payment intent."
                    )

                return existing

            existing = self._records.get(
                record.paypal_binding_id
            )

            if existing is not None:
                if existing != record:
                    raise ValueError(
                        "PayPal binding ID already exists."
                    )

                return existing

            candidate = dict(
                self._records
            )

            candidate[
                record.paypal_binding_id
            ] = record

            self._write_records(
                candidate
            )

            intent_index = dict(
                self._binding_id_by_intent_id
            )
            intent_index[
                record.payment_intent_id
            ] = record.paypal_binding_id

            paypal_index = dict(
                self._binding_id_by_paypal_order_id
            )
            paypal_index[
                record.paypal_order_id
            ] = record.paypal_binding_id

            self._records = candidate
            self._binding_id_by_intent_id = (
                intent_index
            )
            self._binding_id_by_paypal_order_id = (
                paypal_index
            )

            return record

    def get(
        self,
        *,
        paypal_binding_id: str,
    ) -> CustomerPayPalOrderBindingRecord | None:
        self._require_ready()

        normalized = (
            PayPalOrderCreationResult
            ._normalize_required_string(
                paypal_binding_id,
                name="paypal_binding_id",
            )
        )

        return self._records.get(
            normalized
        )

    def get_by_payment_intent_id(
        self,
        *,
        payment_intent_id: str,
    ) -> CustomerPayPalOrderBindingRecord | None:
        self._require_ready()

        normalized = (
            PayPalOrderCreationResult
            ._normalize_required_string(
                payment_intent_id,
                name="payment_intent_id",
            )
        )

        binding_id = (
            self._binding_id_by_intent_id.get(
                normalized
            )
        )

        if binding_id is None:
            return None

        return self._records[
            binding_id
        ]

    def get_by_paypal_order_id(
        self,
        *,
        paypal_order_id: str,
    ) -> CustomerPayPalOrderBindingRecord | None:
        self._require_ready()

        normalized = (
            PayPalOrderCreationResult
            ._normalize_required_string(
                paypal_order_id,
                name="paypal_order_id",
            )
        )

        binding_id = (
            self._binding_id_by_paypal_order_id.get(
                normalized
            )
        )

        if binding_id is None:
            return None

        return self._records[
            binding_id
        ]

    def all(
        self,
    ) -> tuple[
        CustomerPayPalOrderBindingRecord,
        ...,
    ]:
        self._require_ready()

        return tuple(
            self._records[
                binding_id
            ]
            for binding_id in sorted(
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
                "Customer PayPal order binding store "
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
                "Customer PayPal order binding store "
                "is unreadable."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Customer PayPal order binding store "
                "must contain an object."
            )

        if set(
            payload
        ) != {
            "version",
            "records",
        }:
            raise ValueError(
                "Customer PayPal order binding store "
                "has invalid fields."
            )

        if (
            payload["version"]
            != STORE_VERSION
        ):
            raise ValueError(
                "Unsupported customer PayPal order "
                "binding store version."
            )

        items = payload[
            "records"
        ]

        if not isinstance(
            items,
            list,
        ):
            raise ValueError(
                "Customer PayPal order binding records "
                "must be a list."
            )

        restored: dict[
            str,
            CustomerPayPalOrderBindingRecord,
        ] = {}

        intent_index: dict[
            str,
            str,
        ] = {}

        paypal_index: dict[
            str,
            str,
        ] = {}

        for item in items:
            if not isinstance(
                item,
                dict,
            ):
                raise ValueError(
                    "Customer PayPal order binding item "
                    "must be an object."
                )

            if set(
                item
            ) != {
                "paypal_binding_id",
                "paypal_order_id",
                "paypal_request_id",
                "payment_intent_id",
                "order_id",
                "amount_minor",
                "currency",
                "status",
            }:
                raise ValueError(
                    "Customer PayPal order binding item "
                    "has invalid fields."
                )

            try:
                record = (
                    CustomerPayPalOrderBindingRecord(
                        paypal_binding_id=item[
                            "paypal_binding_id"
                        ],
                        paypal_order_id=item[
                            "paypal_order_id"
                        ],
                        paypal_request_id=item[
                            "paypal_request_id"
                        ],
                        payment_intent_id=item[
                            "payment_intent_id"
                        ],
                        order_id=item[
                            "order_id"
                        ],
                        amount_minor=item[
                            "amount_minor"
                        ],
                        currency=item[
                            "currency"
                        ],
                        status=(
                            CustomerPayPalOrderBindingStatus(
                                item[
                                    "status"
                                ]
                            )
                        ),
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Customer PayPal order binding item "
                    "is invalid."
                ) from exc

            if (
                record.paypal_binding_id
                in restored
            ):
                raise ValueError(
                    "Duplicate PayPal binding ID."
                )

            if (
                record.payment_intent_id
                in intent_index
            ):
                raise ValueError(
                    "Duplicate PayPal binding "
                    "payment intent."
                )

            if (
                record.paypal_order_id
                in paypal_index
            ):
                raise ValueError(
                    "Duplicate PayPal order ID."
                )

            restored[
                record.paypal_binding_id
            ] = record

            intent_index[
                record.payment_intent_id
            ] = record.paypal_binding_id

            paypal_index[
                record.paypal_order_id
            ] = record.paypal_binding_id

        self._records = restored
        self._binding_id_by_intent_id = (
            intent_index
        )
        self._binding_id_by_paypal_order_id = (
            paypal_index
        )
        self._ready = True

    def _write_records(
        self,
        records: dict[
            str,
            CustomerPayPalOrderBindingRecord,
        ],
    ) -> None:
        items = []

        for binding_id in sorted(
            records
        ):
            record = records[
                binding_id
            ]

            items.append(
                {
                    "paypal_binding_id": (
                        record.paypal_binding_id
                    ),
                    "paypal_order_id": (
                        record.paypal_order_id
                    ),
                    "paypal_request_id": (
                        record.paypal_request_id
                    ),
                    "payment_intent_id": (
                        record.payment_intent_id
                    ),
                    "order_id": (
                        record.order_id
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


class CustomerPayPalOrderBindingService:
    """
    Bind one authoritative TODOBA PAYPAL intent to one PayPal order.
    """

    def __init__(
        self,
        *,
        binding_store: CustomerPayPalOrderBindingStore,
        payment_intent_store: CustomerPaymentIntentStore,
        order_store: CustomerCommercialOrderStore,
    ) -> None:
        if not isinstance(
            binding_store,
            CustomerPayPalOrderBindingStore,
        ):
            raise TypeError(
                "binding_store must be "
                "CustomerPayPalOrderBindingStore."
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

        if not binding_store.is_ready():
            raise RuntimeError(
                "Customer PayPal order binding store "
                "is not initialized."
            )

        if not payment_intent_store.is_ready():
            raise RuntimeError(
                "Customer payment intent store "
                "is not initialized."
            )

        if not order_store.is_ready():
            raise RuntimeError(
                "Customer commercial order store "
                "is not initialized."
            )

        self._binding_store = binding_store
        self._payment_intent_store = (
            payment_intent_store
        )
        self._order_store = order_store
        self._lock = threading.RLock()

    def bind(
        self,
        *,
        authorized_payment_intent: CustomerPaymentIntentResult,
        paypal_order: PayPalOrderCreationResult,
    ) -> CustomerPayPalOrderBindingRecord:
        if not isinstance(
            authorized_payment_intent,
            CustomerPaymentIntentResult,
        ):
            raise TypeError(
                "authorized_payment_intent must be "
                "CustomerPaymentIntentResult."
            )

        if not isinstance(
            paypal_order,
            PayPalOrderCreationResult,
        ):
            raise TypeError(
                "paypal_order must be "
                "PayPalOrderCreationResult."
            )

        with self._lock:
            self._require_sources_ready()

            authoritative_intent = (
                self._payment_intent_store.get(
                    payment_intent_id=(
                        authorized_payment_intent
                        .payment_intent_id
                    )
                )
            )

            if authoritative_intent is None:
                raise ValueError(
                    "Payment intent is not authoritative."
                )

            if (
                authoritative_intent
                .payment_intent_request_id
                != authorized_payment_intent
                .payment_intent_request_id
                or authoritative_intent
                .payment_intent_id
                != authorized_payment_intent
                .payment_intent_id
                or authoritative_intent.order_id
                != authorized_payment_intent.order_id
                or authoritative_intent.payment_rail
                is not authorized_payment_intent.payment_rail
                or authoritative_intent.status
                is not authorized_payment_intent.status
            ):
                raise ValueError(
                    "Payment intent is not authoritative."
                )

            if (
                authoritative_intent.status
                is not CustomerPaymentIntentStatus.PENDING
            ):
                raise ValueError(
                    "Payment intent is not eligible "
                    "for PayPal binding."
                )

            if (
                authoritative_intent.payment_rail
                is not PaymentRail.PAYPAL
            ):
                raise ValueError(
                    "Payment intent rail must be PAYPAL."
                )

            authoritative_order = (
                self._order_store.get(
                    order_id=(
                        authoritative_intent.order_id
                    )
                )
            )

            if authoritative_order is None:
                raise ValueError(
                    "Commercial order is not authoritative."
                )

            if (
                authoritative_order.order_id
                != authoritative_intent.order_id
                or authoritative_order.status
                is not CustomerCommercialOrderStatus.PENDING
            ):
                raise ValueError(
                    "Commercial order is not authoritative."
                )

            if (
                authoritative_order.currency
                not in _PAYPAL_PAYMENT_CURRENCIES
            ):
                raise ValueError(
                    "Commercial order currency is not "
                    "supported for PayPal payments."
                )

            if (
                paypal_order.paypal_request_id
                != authoritative_intent.payment_intent_id
                or paypal_order.custom_id
                != authoritative_intent.payment_intent_id
                or paypal_order.amount_minor
                != authoritative_order.amount_minor
                or paypal_order.currency
                != authoritative_order.currency
            ):
                raise ValueError(
                    "PayPal order result does not match "
                    "authoritative commercial facts."
                )

            existing_intent = (
                self._binding_store
                .get_by_payment_intent_id(
                    payment_intent_id=(
                        authoritative_intent.payment_intent_id
                    )
                )
            )

            if existing_intent is not None:
                if (
                    existing_intent.paypal_order_id
                    != paypal_order.paypal_order_id
                    or existing_intent.paypal_request_id
                    != paypal_order.paypal_request_id
                    or existing_intent.order_id
                    != authoritative_order.order_id
                    or existing_intent.amount_minor
                    != authoritative_order.amount_minor
                    or existing_intent.currency
                    != authoritative_order.currency
                ):
                    raise ValueError(
                        "Payment intent is already bound "
                        "to different PayPal order facts."
                    )

                return existing_intent

            existing_paypal_order = (
                self._binding_store
                .get_by_paypal_order_id(
                    paypal_order_id=(
                        paypal_order.paypal_order_id
                    )
                )
            )

            if existing_paypal_order is not None:
                if (
                    existing_paypal_order.payment_intent_id
                    != authoritative_intent.payment_intent_id
                ):
                    raise ValueError(
                        "PayPal order is already bound "
                        "to another payment intent."
                    )

                return existing_paypal_order

            record = self._create_bound_record(
                paypal_order=paypal_order,
                payment_intent_id=(
                    authoritative_intent.payment_intent_id
                ),
                order_id=authoritative_order.order_id,
                amount_minor=(
                    authoritative_order.amount_minor
                ),
                currency=authoritative_order.currency,
            )

            return self._binding_store.register(
                record
            )

    def get(
        self,
        *,
        paypal_binding_id: str,
    ) -> CustomerPayPalOrderBindingRecord | None:
        self._require_sources_ready()

        return self._binding_store.get(
            paypal_binding_id=paypal_binding_id
        )

    def _create_bound_record(
        self,
        *,
        paypal_order: PayPalOrderCreationResult,
        payment_intent_id: str,
        order_id: str,
        amount_minor: int,
        currency: str,
    ) -> CustomerPayPalOrderBindingRecord:
        for _ in range(
            _ID_GENERATION_ATTEMPTS
        ):
            paypal_binding_id = (
                "paypal-order-binding-"
                f"{uuid.uuid4().hex}"
            )

            if (
                self._binding_store.get(
                    paypal_binding_id=(
                        paypal_binding_id
                    )
                )
                is not None
            ):
                continue

            return CustomerPayPalOrderBindingRecord(
                paypal_binding_id=paypal_binding_id,
                paypal_order_id=(
                    paypal_order.paypal_order_id
                ),
                paypal_request_id=(
                    paypal_order.paypal_request_id
                ),
                payment_intent_id=payment_intent_id,
                order_id=order_id,
                amount_minor=amount_minor,
                currency=currency,
                status=(
                    CustomerPayPalOrderBindingStatus.BOUND
                ),
            )

        raise RuntimeError(
            "Unable to generate unique PayPal "
            "order binding identity."
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._binding_store.is_ready():
            raise RuntimeError(
                "Customer PayPal order binding store "
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
