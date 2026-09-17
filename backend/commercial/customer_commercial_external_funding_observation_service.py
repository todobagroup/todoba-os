"""
TODOBA Customer Commercial External Funding Observation

Durable in-cycle observation of broker-qualified customer
external funding.

P9A4C owns:

- immutable external-funding observation records
- durable replay identity:
      (account_fingerprint, deal_ticket)
- identical retry idempotency
- conflicting replay rejection
- cycle existence validation
- restart-safe persistence

P9A4C deliberately does not:

- classify raw MT5 evidence
- infer deposits or withdrawals
- price commercial tiers
- apply licensed-cap grace
- decide upgrade or downgrade
- block runtime execution
- own payment, settlement, or entitlement authority

Only classifications already proven as
``external_deposit`` or ``external_withdrawal`` may be
persisted. ``unknown`` and ``not_external`` are never
funding observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
import os
from pathlib import Path
import threading
from typing import Literal

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineStore,
)

from backend.trading.lifecycle.mt5_external_funding_classifier import (
    MT5ExternalFundingClassification,
)


STORE_VERSION = 1


CustomerCommercialExternalFundingKind = Literal[
    "external_deposit",
    "external_withdrawal",
]


@dataclass(
    frozen=True,
)
class CustomerCommercialExternalFundingObservationRecord:
    """
    Immutable durable observation of one broker funding event.
    """

    cycle_id: str
    account_fingerprint: str
    deal_ticket: int
    funding_kind: CustomerCommercialExternalFundingKind
    amount: Decimal

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
            "account_fingerprint",
            self._normalize_required_string(
                self.account_fingerprint,
                name="account_fingerprint",
            ),
        )

        if (
            isinstance(
                self.deal_ticket,
                bool,
            )
            or not isinstance(
                self.deal_ticket,
                int,
            )
            or self.deal_ticket <= 0
        ):
            raise ValueError(
                "deal_ticket must be a positive int."
            )

        if self.funding_kind not in (
            "external_deposit",
            "external_withdrawal",
        ):
            raise ValueError(
                "funding_kind must be external funding."
            )

        if not isinstance(
            self.amount,
            Decimal,
        ):
            raise TypeError(
                "amount must be Decimal."
            )

        if not self.amount.is_finite():
            raise ValueError(
                "amount must be finite."
            )

        if (
            self.funding_kind == "external_deposit"
            and self.amount <= Decimal("0")
        ):
            raise ValueError(
                "external_deposit amount must be positive."
            )

        if (
            self.funding_kind == "external_withdrawal"
            and self.amount >= Decimal("0")
        ):
            raise ValueError(
                "external_withdrawal amount must be negative."
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


class CustomerCommercialExternalFundingObservationStore:
    """
    Durable immutable external-funding observation store.

    Global broker-event replay identity:

        (account_fingerprint, deal_ticket)

    cycle_id is intentionally not part of replay identity.
    This prevents one broker event from being counted again
    in another commercial billing cycle.

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
            tuple[str, int],
            CustomerCommercialExternalFundingObservationRecord,
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
                    "External funding observation store "
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
                    "External funding observation store "
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
                    "External funding observation store "
                    "cannot be loaded."
                ) from error

            if not isinstance(
                payload,
                dict,
            ):
                raise RuntimeError(
                    "External funding observation store "
                    "must be object."
                )

            if (
                payload.get(
                    "version"
                )
                != STORE_VERSION
            ):
                raise RuntimeError(
                    "Unsupported external funding "
                    "observation store version."
                )

            raw_records = payload.get(
                "records"
            )

            if not isinstance(
                raw_records,
                list,
            ):
                raise RuntimeError(
                    "External funding observation records "
                    "must be list."
                )

            loaded: dict[
                tuple[str, int],
                CustomerCommercialExternalFundingObservationRecord,
            ] = {}

            for raw in raw_records:
                record = self._decode_record(
                    raw
                )

                replay_key = self._replay_key(
                    account_fingerprint=(
                        record.account_fingerprint
                    ),
                    deal_ticket=(
                        record.deal_ticket
                    ),
                )

                if replay_key in loaded:
                    raise RuntimeError(
                        "Duplicate external funding "
                        "replay identity in durable store."
                    )

                loaded[
                    replay_key
                ] = record

            self._records = loaded
            self._ready = True

    def save(
        self,
        record: CustomerCommercialExternalFundingObservationRecord,
    ) -> CustomerCommercialExternalFundingObservationRecord:
        if not isinstance(
            record,
            CustomerCommercialExternalFundingObservationRecord,
        ):
            raise TypeError(
                "record must be "
                "CustomerCommercialExternalFundingObservationRecord."
            )

        replay_key = self._replay_key(
            account_fingerprint=(
                record.account_fingerprint
            ),
            deal_ticket=(
                record.deal_ticket
            ),
        )

        with self._lock:
            self._require_ready()

            existing = self._records.get(
                replay_key
            )

            if existing is not None:
                if existing == record:
                    return existing

                raise ValueError(
                    "External funding replay identity "
                    "is already bound to different "
                    "authoritative facts."
                )

            next_records = dict(
                self._records
            )

            next_records[
                replay_key
            ] = record

            self._persist(
                next_records
            )

            self._records = next_records

            return record

    def get_by_replay_identity(
        self,
        *,
        account_fingerprint: str,
        deal_ticket: int,
    ) -> (
        CustomerCommercialExternalFundingObservationRecord
        | None
    ):
        normalized_account = (
            CustomerCommercialExternalFundingObservationRecord
            ._normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        if (
            isinstance(
                deal_ticket,
                bool,
            )
            or not isinstance(
                deal_ticket,
                int,
            )
            or deal_ticket <= 0
        ):
            raise ValueError(
                "deal_ticket must be a positive int."
            )

        with self._lock:
            self._require_ready()

            return self._records.get(
                (
                    normalized_account,
                    deal_ticket,
                )
            )

    @staticmethod
    def _replay_key(
        *,
        account_fingerprint: str,
        deal_ticket: int,
    ) -> tuple[str, int]:
        return (
            account_fingerprint,
            deal_ticket,
        )

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "External funding observation store "
                "is not initialized."
            )

    def _persist(
        self,
        records: dict[
            tuple[str, int],
            CustomerCommercialExternalFundingObservationRecord,
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
                    records[
                        replay_key
                    ]
                )
                for replay_key
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
        record: CustomerCommercialExternalFundingObservationRecord,
    ) -> dict[str, object]:
        return {
            "cycle_id": record.cycle_id,
            "account_fingerprint": (
                record.account_fingerprint
            ),
            "deal_ticket": record.deal_ticket,
            "funding_kind": record.funding_kind,
            "amount": str(
                record.amount
            ),
        }

    @staticmethod
    def _decode_record(
        raw: object,
    ) -> CustomerCommercialExternalFundingObservationRecord:
        if not isinstance(
            raw,
            dict,
        ):
            raise RuntimeError(
                "External funding observation record "
                "must be object."
            )

        required = {
            "cycle_id",
            "account_fingerprint",
            "deal_ticket",
            "funding_kind",
            "amount",
        }

        if set(
            raw
        ) != required:
            raise RuntimeError(
                "External funding observation record "
                "has unsupported fields."
            )

        try:
            amount = Decimal(
                raw[
                    "amount"
                ]
            )
        except (
            ArithmeticError,
            TypeError,
            ValueError,
        ) as error:
            raise RuntimeError(
                "External funding observation amount "
                "is invalid."
            ) from error

        try:
            return (
                CustomerCommercialExternalFundingObservationRecord(
                    cycle_id=raw[
                        "cycle_id"
                    ],
                    account_fingerprint=raw[
                        "account_fingerprint"
                    ],
                    deal_ticket=raw[
                        "deal_ticket"
                    ],
                    funding_kind=raw[
                        "funding_kind"
                    ],
                    amount=amount,
                )
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise RuntimeError(
                "External funding observation record "
                "is invalid."
            ) from error


class CustomerCommercialExternalFundingObservationService:
    """
    Records broker-qualified funding against an existing cycle.

    The service accepts classifier output only.
    It does not reinterpret MT5 evidence.
    """

    def __init__(
        self,
        *,
        store: CustomerCommercialExternalFundingObservationStore,
        billing_cycle_store: CustomerCommercialBillingCycleBaselineStore,
    ) -> None:
        if not isinstance(
            store,
            CustomerCommercialExternalFundingObservationStore,
        ):
            raise TypeError(
                "store must be "
                "CustomerCommercialExternalFundingObservationStore."
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
                "External funding observation store "
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

    def observe(
        self,
        *,
        cycle_id: str,
        classification: MT5ExternalFundingClassification,
    ) -> CustomerCommercialExternalFundingObservationRecord:
        if not isinstance(
            classification,
            MT5ExternalFundingClassification,
        ):
            raise TypeError(
                "classification must be "
                "MT5ExternalFundingClassification."
            )

        normalized_cycle_id = (
            CustomerCommercialExternalFundingObservationRecord
            ._normalize_required_string(
                cycle_id,
                name="cycle_id",
            )
        )

        if (
            self._billing_cycle_store.get(
                cycle_id=normalized_cycle_id
            )
            is None
        ):
            raise ValueError(
                "Commercial billing cycle does not exist."
            )

        if classification.kind not in (
            "external_deposit",
            "external_withdrawal",
        ):
            raise ValueError(
                "Classification is not proven "
                "external funding."
            )

        record = (
            CustomerCommercialExternalFundingObservationRecord(
                cycle_id=normalized_cycle_id,
                account_fingerprint=(
                    classification.account_fingerprint
                ),
                deal_ticket=(
                    classification.deal_ticket
                ),
                funding_kind=(
                    classification.kind
                ),
                amount=(
                    classification.amount
                ),
            )
        )

        return self._store.save(
            record
        )

    def get_by_replay_identity(
        self,
        *,
        account_fingerprint: str,
        deal_ticket: int,
    ) -> (
        CustomerCommercialExternalFundingObservationRecord
        | None
    ):
        return self._store.get_by_replay_identity(
            account_fingerprint=account_fingerprint,
            deal_ticket=deal_ticket,
        )
