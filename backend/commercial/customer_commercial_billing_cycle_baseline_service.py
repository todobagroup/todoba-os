"""
TODOBA Commercial Billing Cycle Baseline Authority.

Owns immutable durable commercial truth for one billing cycle.

Authority flow:

    customer_id
    + cycle_id
    + cycle_started_at
    + authoritative cycle-start / renewal balance
        ->
    P9A2 Commercial Account USD Price Book
        ->
    immutable durable billing-cycle baseline

The baseline freezes:

- authoritative cycle balance USD
- licensed account cap USD
- standard monthly price USD

This owner deliberately does not:

- observe live broker balance
- classify trading profit or loss
- observe deposits or withdrawals
- apply grace
- enforce upgrades or downgrades
- schedule renewals
- create orders or payment intents
- verify or settle payments
- activate Setup
- grant entitlement
- own runtime trading authority
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import threading

from backend.commercial.customer_commercial_account_price_book import (
    CustomerCommercialAccountPriceBook,
)


STORE_VERSION = 1


@dataclass(
    frozen=True,
)
class CustomerCommercialBillingCycleBaselineRecord:
    """
    Immutable authoritative commercial truth for one cycle.
    """

    cycle_id: str
    customer_id: str
    cycle_started_at: datetime

    authoritative_cycle_balance_usd: Decimal

    licensed_account_cap_usd: int
    standard_monthly_price_usd: int

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "cycle_id",
            self._normalize_required_string(
                self.cycle_id,
                name="cycle_id",
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
            "cycle_started_at",
            self._normalize_datetime(
                self.cycle_started_at
            ),
        )

        object.__setattr__(
            self,
            "authoritative_cycle_balance_usd",
            self._normalize_decimal(
                self.authoritative_cycle_balance_usd
            ),
        )

        for name in (
            "licensed_account_cap_usd",
            "standard_monthly_price_usd",
        ):
            value = getattr(
                self,
                name,
            )

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
                    f"{name} must be int."
                )

            if value <= 0:
                raise ValueError(
                    f"{name} must be positive."
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
    def _normalize_datetime(
        value: datetime,
    ) -> datetime:
        if not isinstance(
            value,
            datetime,
        ):
            raise TypeError(
                "cycle_started_at must be datetime."
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "cycle_started_at must be timezone-aware."
            )

        return value.astimezone(
            UTC
        )

    @staticmethod
    def _normalize_decimal(
        value: Decimal,
    ) -> Decimal:
        if not isinstance(
            value,
            Decimal,
        ):
            raise TypeError(
                "authoritative_cycle_balance_usd "
                "must be Decimal."
            )

        if not value.is_finite():
            raise ValueError(
                "authoritative_cycle_balance_usd "
                "must be finite."
            )

        if value <= 0:
            raise ValueError(
                "authoritative_cycle_balance_usd "
                "must be positive."
            )

        return value


class CustomerCommercialBillingCycleBaselineStore:
    """
    Durable immutable billing-cycle baseline store.

    Durable identity:
        cycle_id

    Persistence rule:
        durable file advances atomically before RAM advances.
    """

    def __init__(
        self,
        path: Path,
    ) -> None:
        if not isinstance(
            path,
            Path,
        ):
            raise TypeError(
                "path must be pathlib.Path."
            )

        self._path = path
        self._lock = threading.RLock()

        self._records: dict[
            str,
            CustomerCommercialBillingCycleBaselineRecord,
        ] = {}

        self._ready = False

    def is_ready(
        self,
    ) -> bool:
        with self._lock:
            return self._ready

    def initialize_empty(
        self,
    ) -> None:
        with self._lock:
            if self._ready:
                return

            if self._path.exists():
                raise RuntimeError(
                    "Billing cycle baseline store "
                    "already exists; load it instead."
                )

            self._persist(
                {}
            )

            self._records = {}
            self._ready = True

    def load(
        self,
    ) -> None:
        with self._lock:
            if not self._path.exists():
                raise RuntimeError(
                    "Billing cycle baseline store "
                    "does not exist."
                )

            try:
                payload = json.loads(
                    self._path.read_text(
                        encoding="utf-8"
                    )
                )
            except (
                OSError,
                json.JSONDecodeError,
            ) as error:
                raise RuntimeError(
                    "Billing cycle baseline store "
                    "cannot be loaded."
                ) from error

            if not isinstance(
                payload,
                dict,
            ):
                raise RuntimeError(
                    "Billing cycle baseline store "
                    "payload must be object."
                )

            if (
                payload.get(
                    "version"
                )
                != STORE_VERSION
            ):
                raise RuntimeError(
                    "Unsupported billing cycle "
                    "baseline store version."
                )

            raw_records = payload.get(
                "records"
            )

            if not isinstance(
                raw_records,
                list,
            ):
                raise RuntimeError(
                    "Billing cycle baseline records "
                    "must be list."
                )

            loaded: dict[
                str,
                CustomerCommercialBillingCycleBaselineRecord,
            ] = {}

            for raw in raw_records:
                record = self._decode_record(
                    raw
                )

                if (
                    record.cycle_id
                    in loaded
                ):
                    raise RuntimeError(
                        "Duplicate billing cycle_id "
                        "in durable store."
                    )

                loaded[
                    record.cycle_id
                ] = record

            self._records = loaded
            self._ready = True

    def get(
        self,
        *,
        cycle_id: str,
    ) -> (
        CustomerCommercialBillingCycleBaselineRecord
        | None
    ):
        normalized_cycle_id = (
            CustomerCommercialBillingCycleBaselineRecord
            ._normalize_required_string(
                cycle_id,
                name="cycle_id",
            )
        )

        with self._lock:
            self._require_ready()

            return self._records.get(
                normalized_cycle_id
            )

    def save(
        self,
        record: CustomerCommercialBillingCycleBaselineRecord,
    ) -> CustomerCommercialBillingCycleBaselineRecord:
        if not isinstance(
            record,
            CustomerCommercialBillingCycleBaselineRecord,
        ):
            raise TypeError(
                "record must be "
                "CustomerCommercialBillingCycleBaselineRecord."
            )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                record.cycle_id
            )

            if existing is not None:
                if existing == record:
                    return existing

                raise ValueError(
                    "billing cycle already exists "
                    "with different authoritative facts."
                )

            next_records = dict(
                self._records
            )

            next_records[
                record.cycle_id
            ] = record

            self._persist(
                next_records
            )

            self._records = next_records

            return record

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Billing cycle baseline store "
                "is not initialized."
            )

    def _persist(
        self,
        records: dict[
            str,
            CustomerCommercialBillingCycleBaselineRecord,
        ],
    ) -> None:
        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "version": STORE_VERSION,
            "records": [
                self._encode_record(
                    records[cycle_id]
                )
                for cycle_id
                in sorted(
                    records
                )
            ],
        }

        serialized = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(
                ",",
                ":",
            ),
            sort_keys=True,
        )

        temporary_path = self._path.with_name(
            self._path.name
            + ".tmp"
        )

        try:
            with temporary_path.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(
                    serialized
                )
                handle.write(
                    "\n"
                )
                handle.flush()
                os.fsync(
                    handle.fileno()
                )

            os.replace(
                temporary_path,
                self._path,
            )
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _encode_record(
        record: CustomerCommercialBillingCycleBaselineRecord,
    ) -> dict[str, object]:
        return {
            "cycle_id": record.cycle_id,
            "customer_id": record.customer_id,
            "cycle_started_at": (
                record.cycle_started_at
                .astimezone(
                    UTC
                )
                .isoformat()
                .replace(
                    "+00:00",
                    "Z",
                )
            ),
            "authoritative_cycle_balance_usd": (
                str(
                    record.authoritative_cycle_balance_usd
                )
            ),
            "licensed_account_cap_usd": (
                record.licensed_account_cap_usd
            ),
            "standard_monthly_price_usd": (
                record.standard_monthly_price_usd
            ),
        }

    @staticmethod
    def _decode_record(
        raw: object,
    ) -> CustomerCommercialBillingCycleBaselineRecord:
        if not isinstance(
            raw,
            dict,
        ):
            raise RuntimeError(
                "Billing cycle baseline record "
                "must be object."
            )

        required = {
            "cycle_id",
            "customer_id",
            "cycle_started_at",
            "authoritative_cycle_balance_usd",
            "licensed_account_cap_usd",
            "standard_monthly_price_usd",
        }

        if set(
            raw
        ) != required:
            raise RuntimeError(
                "Billing cycle baseline record "
                "schema mismatch."
            )

        try:
            cycle_started_at = datetime.fromisoformat(
                str(
                    raw[
                        "cycle_started_at"
                    ]
                ).replace(
                    "Z",
                    "+00:00",
                )
            )

            balance = Decimal(
                str(
                    raw[
                        "authoritative_cycle_balance_usd"
                    ]
                )
            )

            record = (
                CustomerCommercialBillingCycleBaselineRecord(
                    cycle_id=raw[
                        "cycle_id"
                    ],
                    customer_id=raw[
                        "customer_id"
                    ],
                    cycle_started_at=cycle_started_at,
                    authoritative_cycle_balance_usd=balance,
                    licensed_account_cap_usd=raw[
                        "licensed_account_cap_usd"
                    ],
                    standard_monthly_price_usd=raw[
                        "standard_monthly_price_usd"
                    ],
                )
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise RuntimeError(
                "Invalid durable billing cycle "
                "baseline record."
            ) from error

        return record


class CustomerCommercialBillingCycleBaselineService:
    """
    Creates immutable cycle baseline truth from P9A2 pricing.
    """

    def __init__(
        self,
        *,
        store: CustomerCommercialBillingCycleBaselineStore,
        price_book: type[
            CustomerCommercialAccountPriceBook
        ],
    ) -> None:
        if not isinstance(
            store,
            CustomerCommercialBillingCycleBaselineStore,
        ):
            raise TypeError(
                "store must be "
                "CustomerCommercialBillingCycleBaselineStore."
            )

        if (
            price_book
            is not CustomerCommercialAccountPriceBook
        ):
            raise TypeError(
                "price_book must be "
                "CustomerCommercialAccountPriceBook."
            )

        if not store.is_ready():
            raise RuntimeError(
                "Billing cycle baseline store "
                "is not initialized."
            )

        self._store = store
        self._price_book = price_book

    def create(
        self,
        *,
        cycle_id: str,
        customer_id: str,
        cycle_started_at: datetime,
        authoritative_cycle_balance_usd: Decimal,
    ) -> CustomerCommercialBillingCycleBaselineRecord:

        normalized_cycle_id = (
            CustomerCommercialBillingCycleBaselineRecord
            ._normalize_required_string(
                cycle_id,
                name="cycle_id",
            )
        )

        normalized_customer_id = (
            CustomerCommercialBillingCycleBaselineRecord
            ._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        normalized_started_at = (
            CustomerCommercialBillingCycleBaselineRecord
            ._normalize_datetime(
                cycle_started_at
            )
        )

        normalized_balance = (
            CustomerCommercialBillingCycleBaselineRecord
            ._normalize_decimal(
                authoritative_cycle_balance_usd
            )
        )

        quote = self._price_book.quote(
            authoritative_cycle_balance_usd=(
                normalized_balance
            )
        )

        candidate = (
            CustomerCommercialBillingCycleBaselineRecord(
                cycle_id=normalized_cycle_id,
                customer_id=normalized_customer_id,
                cycle_started_at=normalized_started_at,
                authoritative_cycle_balance_usd=(
                    normalized_balance
                ),
                licensed_account_cap_usd=(
                    quote.licensed_account_cap_usd
                ),
                standard_monthly_price_usd=(
                    quote.standard_monthly_price_usd
                ),
            )
        )

        return self._store.save(
            candidate
        )
