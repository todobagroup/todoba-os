"""
TODOBA Customer Commercial FX Snapshot Authority.

P9B1 owns provider-neutral durable publication of exact
authoritative USD/VND FX snapshots.

Durable snapshot identity:

    (
        snapshot_date,
        source_id,
        base_currency,
        quote_currency,
    )

Rules:

- USD is the commercial base currency.
- VND is the quote currency.
- rate is exact Decimal truth supplied by an upstream
  authoritative adapter.
- identical retry is idempotent.
- same durable identity with different facts fails closed.
- durable file advances before RAM advances.

P9B1 deliberately does not:

- perform network requests
- choose a provider endpoint
- schedule daily refresh
- define freshness TTL
- calculate VND order amount
- mutate commercial orders
- verify payments
- own settlement or entitlement authority
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import threading


STORE_VERSION = 1


@dataclass(
    frozen=True,
)
class CustomerCommercialFXSnapshotRecord:
    """
    Immutable provider-neutral authoritative USD/VND snapshot.
    """

    snapshot_date: date
    source_id: str

    base_currency: str
    quote_currency: str

    usd_vnd_rate: Decimal

    published_at: datetime
    fetched_at: datetime

    def __post_init__(
        self,
    ) -> None:
        if (
            isinstance(
                self.snapshot_date,
                datetime,
            )
            or not isinstance(
                self.snapshot_date,
                date,
            )
        ):
            raise TypeError(
                "snapshot_date must be datetime.date."
            )

        object.__setattr__(
            self,
            "source_id",
            self._normalize_required_string(
                self.source_id,
                name="source_id",
            ),
        )

        base = self._normalize_currency(
            self.base_currency,
            name="base_currency",
        )

        quote = self._normalize_currency(
            self.quote_currency,
            name="quote_currency",
        )

        if (
            base != "USD"
            or quote != "VND"
        ):
            raise ValueError(
                "FX snapshot currency pair must be USD/VND."
            )

        object.__setattr__(
            self,
            "base_currency",
            base,
        )

        object.__setattr__(
            self,
            "quote_currency",
            quote,
        )

        if not isinstance(
            self.usd_vnd_rate,
            Decimal,
        ):
            raise TypeError(
                "usd_vnd_rate must be Decimal."
            )

        if (
            not self.usd_vnd_rate.is_finite()
            or self.usd_vnd_rate <= Decimal("0")
        ):
            raise ValueError(
                "usd_vnd_rate must be positive and finite."
            )

        object.__setattr__(
            self,
            "published_at",
            self._normalize_datetime(
                self.published_at,
                name="published_at",
            ),
        )

        object.__setattr__(
            self,
            "fetched_at",
            self._normalize_datetime(
                self.fetched_at,
                name="fetched_at",
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
    def _normalize_currency(
        value: str,
        *,
        name: str,
    ) -> str:
        normalized = (
            CustomerCommercialFXSnapshotRecord
            ._normalize_required_string(
                value,
                name=name,
            )
            .upper()
        )

        if (
            len(normalized) != 3
            or not normalized.isascii()
            or not normalized.isalpha()
        ):
            raise ValueError(
                f"{name} must be a three-letter "
                "ASCII currency code."
            )

        return normalized

    @staticmethod
    def _normalize_datetime(
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


class CustomerCommercialFXSnapshotStore:
    """
    Durable immutable authoritative FX snapshot store.

    Persistence:
        temp file
        -> flush
        -> fsync
        -> atomic replace
        -> RAM advance
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
            tuple[
                date,
                str,
                str,
                str,
            ],
            CustomerCommercialFXSnapshotRecord,
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
                    "Commercial FX snapshot store "
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
                    "Commercial FX snapshot store "
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
                    "Commercial FX snapshot store "
                    "cannot be loaded."
                ) from error

            if not isinstance(
                payload,
                dict,
            ):
                raise RuntimeError(
                    "Commercial FX snapshot store "
                    "must be object."
                )

            if (
                payload.get(
                    "version"
                )
                != STORE_VERSION
            ):
                raise RuntimeError(
                    "Unsupported commercial FX "
                    "snapshot store version."
                )

            raw_records = payload.get(
                "records"
            )

            if not isinstance(
                raw_records,
                list,
            ):
                raise RuntimeError(
                    "Commercial FX snapshot records "
                    "must be list."
                )

            loaded: dict[
                tuple[
                    date,
                    str,
                    str,
                    str,
                ],
                CustomerCommercialFXSnapshotRecord,
            ] = {}

            for raw in raw_records:
                record = self._decode_record(
                    raw
                )

                identity = self._identity(
                    record=record
                )

                if identity in loaded:
                    raise RuntimeError(
                        "Duplicate commercial FX "
                        "snapshot identity in durable store."
                    )

                loaded[
                    identity
                ] = record

            self._records = loaded
            self._ready = True

    def save(
        self,
        record: CustomerCommercialFXSnapshotRecord,
    ) -> CustomerCommercialFXSnapshotRecord:
        if not isinstance(
            record,
            CustomerCommercialFXSnapshotRecord,
        ):
            raise TypeError(
                "record must be "
                "CustomerCommercialFXSnapshotRecord."
            )

        identity = self._identity(
            record=record
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                identity
            )

            if existing is not None:
                if existing == record:
                    return existing

                raise ValueError(
                    "Commercial FX snapshot identity "
                    "already exists with different "
                    "authoritative facts."
                )

            next_records = dict(
                self._records
            )

            next_records[
                identity
            ] = record

            self._persist(
                next_records
            )

            self._records = next_records

            return record

    def get(
        self,
        *,
        snapshot_date: date,
        source_id: str,
        base_currency: str,
        quote_currency: str,
    ) -> (
        CustomerCommercialFXSnapshotRecord
        | None
    ):
        if (
            isinstance(
                snapshot_date,
                datetime,
            )
            or not isinstance(
                snapshot_date,
                date,
            )
        ):
            raise TypeError(
                "snapshot_date must be datetime.date."
            )

        normalized_source = (
            CustomerCommercialFXSnapshotRecord
            ._normalize_required_string(
                source_id,
                name="source_id",
            )
        )

        normalized_base = (
            CustomerCommercialFXSnapshotRecord
            ._normalize_currency(
                base_currency,
                name="base_currency",
            )
        )

        normalized_quote = (
            CustomerCommercialFXSnapshotRecord
            ._normalize_currency(
                quote_currency,
                name="quote_currency",
            )
        )

        if (
            normalized_base != "USD"
            or normalized_quote != "VND"
        ):
            raise ValueError(
                "FX snapshot currency pair must be USD/VND."
            )

        with self._lock:
            self._require_ready()

            return self._records.get(
                (
                    snapshot_date,
                    normalized_source,
                    normalized_base,
                    normalized_quote,
                )
            )

    @staticmethod
    def _identity(
        *,
        record: CustomerCommercialFXSnapshotRecord,
    ) -> tuple[
        date,
        str,
        str,
        str,
    ]:
        return (
            record.snapshot_date,
            record.source_id,
            record.base_currency,
            record.quote_currency,
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Commercial FX snapshot store "
                "is not initialized."
            )

    def _persist(
        self,
        records: dict[
            tuple[
                date,
                str,
                str,
                str,
            ],
            CustomerCommercialFXSnapshotRecord,
        ],
    ) -> None:
        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        ordered = sorted(
            records.items(),
            key=lambda item: (
                item[0][0].isoformat(),
                item[0][1],
                item[0][2],
                item[0][3],
            ),
        )

        payload = {
            "version": STORE_VERSION,
            "records": [
                self._encode_record(
                    record
                )
                for _identity, record in ordered
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
        record: CustomerCommercialFXSnapshotRecord,
    ) -> dict[str, object]:
        return {
            "snapshot_date": (
                record.snapshot_date.isoformat()
            ),
            "source_id": record.source_id,
            "base_currency": record.base_currency,
            "quote_currency": record.quote_currency,
            "usd_vnd_rate": str(
                record.usd_vnd_rate
            ),
            "published_at": (
                CustomerCommercialFXSnapshotStore
                ._encode_datetime(
                    record.published_at
                )
            ),
            "fetched_at": (
                CustomerCommercialFXSnapshotStore
                ._encode_datetime(
                    record.fetched_at
                )
            ),
        }

    @staticmethod
    def _decode_record(
        raw: object,
    ) -> CustomerCommercialFXSnapshotRecord:
        if not isinstance(
            raw,
            dict,
        ):
            raise RuntimeError(
                "Commercial FX snapshot record "
                "must be object."
            )

        required = {
            "snapshot_date",
            "source_id",
            "base_currency",
            "quote_currency",
            "usd_vnd_rate",
            "published_at",
            "fetched_at",
        }

        if set(
            raw
        ) != required:
            raise RuntimeError(
                "Commercial FX snapshot record "
                "has unsupported fields."
            )

        try:
            snapshot_date = date.fromisoformat(
                raw[
                    "snapshot_date"
                ]
            )

            rate = Decimal(
                raw[
                    "usd_vnd_rate"
                ]
            )

            published_at = (
                CustomerCommercialFXSnapshotStore
                ._decode_datetime(
                    raw[
                        "published_at"
                    ]
                )
            )

            fetched_at = (
                CustomerCommercialFXSnapshotStore
                ._decode_datetime(
                    raw[
                        "fetched_at"
                    ]
                )
            )
        except (
            ArithmeticError,
            TypeError,
            ValueError,
        ) as error:
            raise RuntimeError(
                "Commercial FX snapshot record "
                "contains invalid durable values."
            ) from error

        try:
            return CustomerCommercialFXSnapshotRecord(
                snapshot_date=snapshot_date,
                source_id=raw[
                    "source_id"
                ],
                base_currency=raw[
                    "base_currency"
                ],
                quote_currency=raw[
                    "quote_currency"
                ],
                usd_vnd_rate=rate,
                published_at=published_at,
                fetched_at=fetched_at,
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise RuntimeError(
                "Commercial FX snapshot record "
                "is invalid."
            ) from error

    @staticmethod
    def _encode_datetime(
        value: datetime,
    ) -> str:
        return (
            value
            .astimezone(
                UTC
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )

    @staticmethod
    def _decode_datetime(
        raw: object,
    ) -> datetime:
        if not isinstance(
            raw,
            str,
        ):
            raise ValueError(
                "datetime value must be str."
            )

        normalized = raw

        if normalized.endswith(
            "Z"
        ):
            normalized = (
                normalized[:-1]
                + "+00:00"
            )

        value = datetime.fromisoformat(
            normalized
        )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "datetime must be timezone-aware."
            )

        return value.astimezone(
            UTC
        )
