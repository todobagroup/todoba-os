from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineRecord,
    CustomerCommercialBillingCycleBaselineStore,
)


_STORE_VERSION = 1


@dataclass(
    frozen=True,
)
class CustomerCommercialCurrentBillingCycleRecord:
    """
    Explicit authoritative pointer from one customer
    to its current commercial billing cycle.
    """

    customer_id: str
    cycle_id: str

    def __post_init__(
        self,
    ) -> None:
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
            "cycle_id",
            self._normalize_required_string(
                self.cycle_id,
                name="cycle_id",
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


class CustomerCommercialCurrentBillingCycleStore:
    """
    Durable mutable current-cycle pointer authority.

    One customer has at most one current cycle pointer.

    Durable file advances atomically before RAM advances.
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
            CustomerCommercialCurrentBillingCycleRecord,
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
                    "Current billing cycle store "
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
                    "Current billing cycle store "
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
                    "Current billing cycle store "
                    "cannot be loaded."
                ) from error

            if not isinstance(
                payload,
                dict,
            ):
                raise RuntimeError(
                    "Current billing cycle store "
                    "payload must be object."
                )

            if (
                payload.get(
                    "version"
                )
                != _STORE_VERSION
            ):
                raise RuntimeError(
                    "Unsupported current billing cycle "
                    "store version."
                )

            raw_records = payload.get(
                "records"
            )

            if not isinstance(
                raw_records,
                list,
            ):
                raise RuntimeError(
                    "Current billing cycle records "
                    "must be list."
                )

            restored: dict[
                str,
                CustomerCommercialCurrentBillingCycleRecord,
            ] = {}

            for raw in raw_records:
                if (
                    not isinstance(
                        raw,
                        dict,
                    )
                    or set(
                        raw
                    )
                    != {
                        "customer_id",
                        "cycle_id",
                    }
                ):
                    raise RuntimeError(
                        "Current billing cycle record "
                        "payload is invalid."
                    )

                try:
                    record = (
                        CustomerCommercialCurrentBillingCycleRecord(
                            customer_id=raw[
                                "customer_id"
                            ],
                            cycle_id=raw[
                                "cycle_id"
                            ],
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ) as error:
                    raise RuntimeError(
                        "Current billing cycle record "
                        "payload is invalid."
                    ) from error

                if (
                    record.customer_id
                    in restored
                ):
                    raise RuntimeError(
                        "Duplicate current billing cycle "
                        "customer identity."
                    )

                restored[
                    record.customer_id
                ] = record

            self._records = restored
            self._ready = True

    def set_current(
        self,
        record: CustomerCommercialCurrentBillingCycleRecord,
    ) -> CustomerCommercialCurrentBillingCycleRecord:
        if not isinstance(
            record,
            CustomerCommercialCurrentBillingCycleRecord,
        ):
            raise TypeError(
                "record must be "
                "CustomerCommercialCurrentBillingCycleRecord."
            )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                record.customer_id
            )

            if existing == record:
                return existing

            candidate = dict(
                self._records
            )

            candidate[
                record.customer_id
            ] = record

            self._persist(
                candidate
            )

            self._records = candidate

            return record

    def get_current_cycle_id(
        self,
        *,
        customer_id: str,
    ) -> str | None:
        normalized_customer_id = (
            CustomerCommercialCurrentBillingCycleRecord
            ._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        with self._lock:
            self._require_ready()

            record = self._records.get(
                normalized_customer_id
            )

            if record is None:
                return None

            return record.cycle_id

    def all(
        self,
    ) -> tuple[
        CustomerCommercialCurrentBillingCycleRecord,
        ...,
    ]:
        with self._lock:
            self._require_ready()

            return tuple(
                self._records[
                    customer_id
                ]
                for customer_id in sorted(
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

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Current billing cycle store "
                "is not initialized."
            )

    def _persist(
        self,
        records: dict[
            str,
            CustomerCommercialCurrentBillingCycleRecord,
        ],
    ) -> None:
        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "version": _STORE_VERSION,
            "records": [
                {
                    "customer_id": (
                        records[
                            customer_id
                        ].customer_id
                    ),
                    "cycle_id": (
                        records[
                            customer_id
                        ].cycle_id
                    ),
                }
                for customer_id in sorted(
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


class CustomerCommercialCurrentBillingCycleService:
    """
    Resolve an explicitly selected current commercial
    billing cycle.

    This service never infers current-cycle authority from
    cycle timestamps or record ordering.
    """

    def __init__(
        self,
        *,
        store: CustomerCommercialCurrentBillingCycleStore,
        billing_cycle_store: CustomerCommercialBillingCycleBaselineStore,
    ) -> None:
        if not isinstance(
            store,
            CustomerCommercialCurrentBillingCycleStore,
        ):
            raise TypeError(
                "store must be "
                "CustomerCommercialCurrentBillingCycleStore."
            )

        if not isinstance(
            billing_cycle_store,
            CustomerCommercialBillingCycleBaselineStore,
        ):
            raise TypeError(
                "billing_cycle_store must be "
                "CustomerCommercialBillingCycleBaselineStore."
            )

        if not store.is_ready():
            raise RuntimeError(
                "Current billing cycle store "
                "is not initialized."
            )

        if not billing_cycle_store.is_ready():
            raise RuntimeError(
                "Billing cycle baseline store "
                "is not initialized."
            )

        self._store = store
        self._billing_cycle_store = (
            billing_cycle_store
        )

    def set_current(
        self,
        *,
        customer_id: str,
        cycle_id: str,
    ) -> CustomerCommercialBillingCycleBaselineRecord:
        normalized_customer_id = (
            CustomerCommercialCurrentBillingCycleRecord
            ._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        normalized_cycle_id = (
            CustomerCommercialCurrentBillingCycleRecord
            ._normalize_required_string(
                cycle_id,
                name="cycle_id",
            )
        )

        baseline = self._billing_cycle_store.get(
            cycle_id=normalized_cycle_id
        )

        if baseline is None:
            raise RuntimeError(
                "Authoritative billing cycle "
                "does not exist."
            )

        if (
            baseline.customer_id
            != normalized_customer_id
        ):
            raise RuntimeError(
                "Billing cycle customer does not "
                "match current-cycle customer."
            )

        self._store.set_current(
            CustomerCommercialCurrentBillingCycleRecord(
                customer_id=normalized_customer_id,
                cycle_id=normalized_cycle_id,
            )
        )

        return baseline

    def resolve_current(
        self,
        *,
        customer_id: str,
    ) -> CustomerCommercialBillingCycleBaselineRecord:
        normalized_customer_id = (
            CustomerCommercialCurrentBillingCycleRecord
            ._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        cycle_id = (
            self._store.get_current_cycle_id(
                customer_id=normalized_customer_id
            )
        )

        if cycle_id is None:
            raise RuntimeError(
                "Authoritative current billing cycle "
                "is not configured."
            )

        baseline = self._billing_cycle_store.get(
            cycle_id=cycle_id
        )

        if baseline is None:
            raise RuntimeError(
                "Authoritative current billing cycle "
                "baseline is missing."
            )

        if (
            baseline.customer_id
            != normalized_customer_id
        ):
            raise RuntimeError(
                "Current billing cycle customer "
                "does not match authoritative baseline."
            )

        return baseline
