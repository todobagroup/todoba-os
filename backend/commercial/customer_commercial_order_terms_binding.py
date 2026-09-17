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
class CustomerCommercialOrderTermsBindingRecord:
    """
    Durable immutable purchased commercial terms bound to one
    authoritative commercial order.

    This truth contains no payment, settlement, entitlement,
    deployment, activation, or runtime authority.
    """

    order_id: str
    customer_id: str
    licensed_account_cap_usd: int
    standard_monthly_price_usd: int

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "order_id",
            self._normalize_required_string(
                self.order_id,
                name="order_id",
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
            "licensed_account_cap_usd",
            self._normalize_positive_int(
                self.licensed_account_cap_usd,
                name="licensed_account_cap_usd",
            ),
        )
        object.__setattr__(
            self,
            "standard_monthly_price_usd",
            self._normalize_positive_int(
                self.standard_monthly_price_usd,
                name="standard_monthly_price_usd",
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

    @staticmethod
    def _normalize_positive_int(
        value: int,
        *,
        name: str,
    ) -> int:
        if (
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                f"{name} must be int."
            )

        if value <= 0:
            raise ValueError(
                f"{name} must be positive."
            )

        return value


class CustomerCommercialOrderTermsBindingStore:
    """
    Durable immutable order ? purchased-commercial-terms authority.

    Primary identity:
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
            CustomerCommercialOrderTermsBindingRecord,
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
                    "Order terms binding store already exists."
                )

            self.storage_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._records = {}
            self._persist_records(
                self._records
            )
            self._ready = True

    def open_existing(
        self,
    ) -> None:
        with self._lock:
            if not self.storage_path.exists():
                raise RuntimeError(
                    "Order terms binding store does not exist."
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
                    "Order terms binding store could not be opened."
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
                    "records",
                }
                or payload.get(
                    "version"
                )
                != _STORE_VERSION
                or not isinstance(
                    payload.get(
                        "records"
                    ),
                    list,
                )
            ):
                raise RuntimeError(
                    "Order terms binding store payload is invalid."
                )

            restored: dict[
                str,
                CustomerCommercialOrderTermsBindingRecord,
            ] = {}

            for raw in payload[
                "records"
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
                        "order_id",
                        "customer_id",
                        "licensed_account_cap_usd",
                        "standard_monthly_price_usd",
                    }
                ):
                    raise RuntimeError(
                        "Order terms binding record payload is invalid."
                    )

                try:
                    record = (
                        CustomerCommercialOrderTermsBindingRecord(
                            order_id=raw[
                                "order_id"
                            ],
                            customer_id=raw[
                                "customer_id"
                            ],
                            licensed_account_cap_usd=raw[
                                "licensed_account_cap_usd"
                            ],
                            standard_monthly_price_usd=raw[
                                "standard_monthly_price_usd"
                            ],
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ) as exc:
                    raise RuntimeError(
                        "Order terms binding record payload is invalid."
                    ) from exc

                if (
                    record.order_id
                    in restored
                ):
                    raise RuntimeError(
                        "Duplicate order terms binding order ID."
                    )

                restored[
                    record.order_id
                ] = record

            self._records = restored
            self._ready = True

    def is_ready(
        self,
    ) -> bool:
        with self._lock:
            return self._ready

    def register(
        self,
        record: CustomerCommercialOrderTermsBindingRecord,
    ) -> CustomerCommercialOrderTermsBindingRecord:
        if not isinstance(
            record,
            CustomerCommercialOrderTermsBindingRecord,
        ):
            raise TypeError(
                "Order terms binding store requires "
                "CustomerCommercialOrderTermsBindingRecord."
            )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                record.order_id
            )

            if existing is not None:
                if existing != record:
                    raise ValueError(
                        "order is already bound "
                        "to different commercial terms."
                    )

                return existing

            candidate = dict(
                self._records
            )
            candidate[
                record.order_id
            ] = record

            self._persist_records(
                candidate
            )

            self._records = candidate

            return record

    def get_by_order_id(
        self,
        *,
        order_id: str,
    ) -> (
        CustomerCommercialOrderTermsBindingRecord
        | None
    ):
        normalized = (
            CustomerCommercialOrderTermsBindingRecord
            ._normalize_required_string(
                order_id,
                name="order_id",
            )
        )

        with self._lock:
            self._require_ready()

            return self._records.get(
                normalized
            )

    def all(
        self,
    ) -> tuple[
        CustomerCommercialOrderTermsBindingRecord,
        ...,
    ]:
        with self._lock:
            self._require_ready()

            return tuple(
                self._records[
                    order_id
                ]
                for order_id in sorted(
                    self._records
                )
            )

    def size(
        self,
    ) -> int:
        with self._lock:
            self._require_ready()

            return len(
                self._records
            )

    def _persist_records(
        self,
        records: dict[
            str,
            CustomerCommercialOrderTermsBindingRecord,
        ],
    ) -> None:
        payload = {
            "version": _STORE_VERSION,
            "records": [
                {
                    "order_id": (
                        records[
                            order_id
                        ].order_id
                    ),
                    "customer_id": (
                        records[
                            order_id
                        ].customer_id
                    ),
                    "licensed_account_cap_usd": (
                        records[
                            order_id
                        ].licensed_account_cap_usd
                    ),
                    "standard_monthly_price_usd": (
                        records[
                            order_id
                        ].standard_monthly_price_usd
                    ),
                }
                for order_id in sorted(
                    records
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
                "Order terms binding store could not be persisted."
            ) from exc

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Order terms binding store is not initialized."
            )
