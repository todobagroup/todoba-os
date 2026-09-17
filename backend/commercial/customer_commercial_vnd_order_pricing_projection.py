from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from decimal import ROUND_HALF_DOWN
from decimal import localcontext
from pathlib import Path

from backend.commercial.customer_commercial_fx_freshness_gate import (
    CustomerCommercialFXFreshnessGate,
)


UTC = timezone.utc
_STORE_VERSION = 1
_VND_QUANTUM = Decimal("1")


@dataclass(
    frozen=True,
)
class CustomerCommercialVndOrderPricingProjectionRecord:
    """
    Durable immutable server-side pricing truth for one VND order
    projection.

    FX determines VND pricing exactly once. This record does not
    create an order, payment intent, settlement, entitlement, or
    activation.
    """

    pricing_request_id: str
    customer_id: str
    usd_price: Decimal
    fx_snapshot_date: date
    fx_source_id: str
    fx_usd_vnd_rate: Decimal
    fx_published_at: datetime
    amount_minor: int
    currency: str

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "pricing_request_id",
            self._normalize_required_string(
                self.pricing_request_id,
                name="pricing_request_id",
            ),
        )
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
            "fx_source_id",
            self._normalize_required_string(
                self.fx_source_id,
                name="fx_source_id",
            ),
        )

        object.__setattr__(
            self,
            "usd_price",
            self._normalize_positive_decimal(
                self.usd_price,
                name="usd_price",
            ),
        )
        object.__setattr__(
            self,
            "fx_usd_vnd_rate",
            self._normalize_positive_decimal(
                self.fx_usd_vnd_rate,
                name="fx_usd_vnd_rate",
            ),
        )

        if not isinstance(
            self.fx_snapshot_date,
            date,
        ) or isinstance(
            self.fx_snapshot_date,
            datetime,
        ):
            raise TypeError(
                "fx_snapshot_date must be date."
            )

        object.__setattr__(
            self,
            "fx_published_at",
            self._normalize_aware_datetime(
                self.fx_published_at,
                name="fx_published_at",
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
                "VND pricing projection currency must be VND."
            )

        object.__setattr__(
            self,
            "currency",
            normalized_currency,
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

    @staticmethod
    def _normalize_positive_decimal(
        value: Decimal,
        *,
        name: str,
    ) -> Decimal:
        if not isinstance(
            value,
            Decimal,
        ):
            raise TypeError(
                f"{name} must be Decimal."
            )

        if (
            not value.is_finite()
            or value <= Decimal("0")
        ):
            raise ValueError(
                f"{name} must be a positive finite Decimal."
            )

        return value

    @staticmethod
    def _normalize_aware_datetime(
        value: datetime,
        *,
        name: str,
    ) -> datetime:
        if not isinstance(
            value,
            datetime,
        ):
            raise TypeError(
                f"{name} must be datetime."
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                f"{name} must be timezone-aware."
            )

        return value.astimezone(
            UTC
        )


class CustomerCommercialVndOrderPricingProjectionStore:
    """
    Durable owner of immutable VND pricing projections.

    Primary and idempotency identity:
        pricing_request_id
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
            CustomerCommercialVndOrderPricingProjectionRecord,
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
                    "VND pricing projection store already exists."
                )

            self.storage_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._records = {}
            self._persist()
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if not self.storage_path.exists():
                raise RuntimeError(
                    "VND pricing projection store does not exist."
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
                    "VND pricing projection store could not be opened."
                ) from exc

            if (
                not isinstance(
                    payload,
                    dict,
                )
                or payload.get("version")
                != _STORE_VERSION
                or not isinstance(
                    payload.get("records"),
                    list,
                )
            ):
                raise RuntimeError(
                    "VND pricing projection store payload is invalid."
                )

            records: dict[
                str,
                CustomerCommercialVndOrderPricingProjectionRecord,
            ] = {}

            for raw in payload["records"]:
                if not isinstance(
                    raw,
                    dict,
                ):
                    raise RuntimeError(
                        "VND pricing projection record payload is invalid."
                    )

                try:
                    record = (
                        CustomerCommercialVndOrderPricingProjectionRecord(
                            pricing_request_id=raw[
                                "pricing_request_id"
                            ],
                            customer_id=raw[
                                "customer_id"
                            ],
                            usd_price=Decimal(
                                raw[
                                    "usd_price"
                                ]
                            ),
                            fx_snapshot_date=date.fromisoformat(
                                raw[
                                    "fx_snapshot_date"
                                ]
                            ),
                            fx_source_id=raw[
                                "fx_source_id"
                            ],
                            fx_usd_vnd_rate=Decimal(
                                raw[
                                    "fx_usd_vnd_rate"
                                ]
                            ),
                            fx_published_at=datetime.fromisoformat(
                                raw[
                                    "fx_published_at"
                                ]
                            ),
                            amount_minor=raw[
                                "amount_minor"
                            ],
                            currency=raw[
                                "currency"
                            ],
                        )
                    )
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    raise RuntimeError(
                        "VND pricing projection record payload is invalid."
                    ) from exc

                if (
                    record.pricing_request_id
                    in records
                ):
                    raise RuntimeError(
                        "Duplicate pricing_request_id."
                    )

                records[
                    record.pricing_request_id
                ] = record

            self._records = records
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        with self._lock:
            return self._ready

    def register(
        self,
        record: CustomerCommercialVndOrderPricingProjectionRecord,
    ) -> CustomerCommercialVndOrderPricingProjectionRecord:
        if not isinstance(
            record,
            CustomerCommercialVndOrderPricingProjectionRecord,
        ):
            raise TypeError(
                "VND pricing projection store requires "
                "CustomerCommercialVndOrderPricingProjectionRecord."
            )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                record.pricing_request_id
            )

            if existing is not None:
                if existing != record:
                    raise ValueError(
                        "pricing request is already bound "
                        "to different pricing facts."
                    )

                return existing

            candidate = dict(
                self._records
            )
            candidate[
                record.pricing_request_id
            ] = record

            self._write_records(
                candidate
            )

            self._records = candidate

            return record

    def get_by_pricing_request_id(
        self,
        *,
        pricing_request_id: str,
    ) -> (
        CustomerCommercialVndOrderPricingProjectionRecord
        | None
    ):
        normalized = (
            CustomerCommercialVndOrderPricingProjectionRecord
            ._normalize_required_string(
                pricing_request_id,
                name="pricing_request_id",
            )
        )

        with self._lock:
            self._require_ready()
            return self._records.get(
                normalized
            )

    def size(
        self,
    ) -> int:
        with self._lock:
            self._require_ready()
            return len(
                self._records
            )

    def _write_records(
        self,
        records: dict[
            str,
            CustomerCommercialVndOrderPricingProjectionRecord,
        ],
    ) -> None:
        payload = {
            "version": _STORE_VERSION,
            "records": [
                self._serialize_record(
                    records[key]
                )
                for key in sorted(
                    records
                )
            ],
        }

        self._write_payload(
            payload
        )

    def _persist(
        self,
    ) -> None:
        self._write_records(
            self._records
        )

    def _write_payload(
        self,
        payload: dict,
    ) -> None:
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.storage_path.with_name(
                f"{self.storage_path.name}.tmp"
            )
        )

        encoded = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
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
                "VND pricing projection store could not be persisted."
            ) from exc

    @staticmethod
    def _serialize_record(
        record: CustomerCommercialVndOrderPricingProjectionRecord,
    ) -> dict:
        return {
            "pricing_request_id": (
                record.pricing_request_id
            ),
            "customer_id": (
                record.customer_id
            ),
            "usd_price": str(
                record.usd_price
            ),
            "fx_snapshot_date": (
                record.fx_snapshot_date.isoformat()
            ),
            "fx_source_id": (
                record.fx_source_id
            ),
            "fx_usd_vnd_rate": str(
                record.fx_usd_vnd_rate
            ),
            "fx_published_at": (
                record.fx_published_at.isoformat()
            ),
            "amount_minor": (
                record.amount_minor
            ),
            "currency": (
                record.currency
            ),
        }

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "VND pricing projection store is not initialized."
            )


class CustomerCommercialVndOrderPricingProjectionService:
    """
    Server-side authority that freezes a USD commercial price into
    an immutable VND pricing projection using one usable
    authoritative FX snapshot.

    This owner does not create commercial orders, payment intents,
    reconciliation, settlement, entitlement, or activation.
    """

    def __init__(
        self,
        *,
        projection_store: CustomerCommercialVndOrderPricingProjectionStore,
        fx_freshness_gate: CustomerCommercialFXFreshnessGate,
    ) -> None:
        if not isinstance(
            projection_store,
            CustomerCommercialVndOrderPricingProjectionStore,
        ):
            raise TypeError(
                "projection_store must be "
                "CustomerCommercialVndOrderPricingProjectionStore."
            )

        if not isinstance(
            fx_freshness_gate,
            CustomerCommercialFXFreshnessGate,
        ):
            raise TypeError(
                "fx_freshness_gate must be "
                "CustomerCommercialFXFreshnessGate."
            )

        self._projection_store = (
            projection_store
        )
        self._fx_freshness_gate = (
            fx_freshness_gate
        )
        self._lock = threading.RLock()

    def create(
        self,
        *,
        pricing_request_id: str,
        customer_id: str,
        usd_price: Decimal,
    ) -> CustomerCommercialVndOrderPricingProjectionRecord:
        normalized_request_id = (
            CustomerCommercialVndOrderPricingProjectionRecord
            ._normalize_required_string(
                pricing_request_id,
                name="pricing_request_id",
            )
        )

        normalized_customer_id = (
            CustomerCommercialVndOrderPricingProjectionRecord
            ._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        normalized_usd_price = (
            CustomerCommercialVndOrderPricingProjectionRecord
            ._normalize_positive_decimal(
                usd_price,
                name="usd_price",
            )
        )

        with self._lock:
            if not self._projection_store.is_ready():
                raise RuntimeError(
                    "VND pricing projection store is not initialized."
                )

            existing = (
                self._projection_store
                .get_by_pricing_request_id(
                    pricing_request_id=(
                        normalized_request_id
                    )
                )
            )

            if existing is not None:
                if (
                    existing.customer_id
                    != normalized_customer_id
                    or existing.usd_price
                    != normalized_usd_price
                ):
                    raise ValueError(
                        "pricing request is already bound "
                        "to different pricing facts."
                    )

                return existing

            snapshot = (
                self._fx_freshness_gate
                .require_usable()
            )

            amount_minor = (
                self._project_vnd_amount(
                    usd_price=normalized_usd_price,
                    usd_vnd_rate=(
                        snapshot.usd_vnd_rate
                    ),
                )
            )

            record = (
                CustomerCommercialVndOrderPricingProjectionRecord(
                    pricing_request_id=(
                        normalized_request_id
                    ),
                    customer_id=(
                        normalized_customer_id
                    ),
                    usd_price=(
                        normalized_usd_price
                    ),
                    fx_snapshot_date=(
                        snapshot.snapshot_date
                    ),
                    fx_source_id=(
                        snapshot.source_id
                    ),
                    fx_usd_vnd_rate=(
                        snapshot.usd_vnd_rate
                    ),
                    fx_published_at=(
                        snapshot.published_at
                    ),
                    amount_minor=(
                        amount_minor
                    ),
                    currency="VND",
                )
            )

            return self._projection_store.register(
                record
            )

    @staticmethod
    def _project_vnd_amount(
        *,
        usd_price: Decimal,
        usd_vnd_rate: Decimal,
    ) -> int:
        usd_digits = len(
            usd_price.as_tuple().digits
        )
        rate_digits = len(
            usd_vnd_rate.as_tuple().digits
        )

        with localcontext() as context:
            context.prec = max(
                50,
                usd_digits
                + rate_digits
                + 10,
            )

            raw_vnd = (
                usd_price
                * usd_vnd_rate
            )

            rounded_vnd = (
                raw_vnd.quantize(
                    _VND_QUANTUM,
                    rounding=ROUND_HALF_DOWN,
                )
            )

        if (
            not rounded_vnd.is_finite()
            or rounded_vnd <= Decimal("0")
        ):
            raise RuntimeError(
                "Projected VND amount is invalid."
            )

        amount_minor = int(
            rounded_vnd
        )

        if amount_minor <= 0:
            raise RuntimeError(
                "Projected VND amount is invalid."
            )

        return amount_minor
