from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import threading


STORE_VERSION = 1


@dataclass(frozen=True)
class CustomerCommercialPendingExposureContainmentIssuanceRecord:
    issuance_id: str
    trigger_id: str

    deployment_id: str
    commercial_entitlement_id: str
    cycle_id: str

    agent_id: str
    account_fingerprint: str
    symbol: str

    mission_id: str
    requested_by_sender_id: int

    created_at: str
    expires_at: str
    sequence: int


class CustomerCommercialPendingExposureContainmentIssuanceStore:
    """
    Durable authority for frozen commercial-containment issuance facts.

    Replay identity:
        (trigger_id, symbol)

    This owner does not:
    - create or deliver ControlMission
    - cancel broker orders
    - mutate pending-order execution state
    - claim broker cancellation success
    """

    def __init__(
        self,
        path: Path,
    ) -> None:
        if not isinstance(path, Path):
            raise TypeError(
                "path must be pathlib.Path."
            )

        self._path = path
        self._lock = threading.RLock()

        self._records: dict[
            tuple[str, str],
            CustomerCommercialPendingExposureContainmentIssuanceRecord,
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
                    "Containment issuance store already exists; "
                    "load it instead."
                )

            self._persist({})

            self._records = {}
            self._ready = True

    def load(
        self,
    ) -> None:
        with self._lock:
            if not self._path.exists():
                raise RuntimeError(
                    "Containment issuance store does not exist."
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
                    "Containment issuance store cannot be loaded."
                ) from error

            if not isinstance(payload, dict):
                raise RuntimeError(
                    "Containment issuance store must be object."
                )

            if payload.get("version") != STORE_VERSION:
                raise RuntimeError(
                    "Unsupported containment issuance "
                    "store version."
                )

            raw_records = payload.get("records")

            if not isinstance(raw_records, list):
                raise RuntimeError(
                    "Containment issuance records must be list."
                )

            loaded: dict[
                tuple[str, str],
                CustomerCommercialPendingExposureContainmentIssuanceRecord,
            ] = {}

            mission_ids: set[str] = set()

            for raw in raw_records:
                record = self._decode_record(
                    raw
                )

                replay_key = self._replay_key(
                    trigger_id=record.trigger_id,
                    symbol=record.symbol,
                )

                if replay_key in loaded:
                    raise RuntimeError(
                        "Duplicate containment issuance "
                        "replay identity."
                    )

                if record.mission_id in mission_ids:
                    raise RuntimeError(
                        "Duplicate containment mission_id "
                        "in durable store."
                    )

                loaded[replay_key] = record
                mission_ids.add(
                    record.mission_id
                )

            self._records = loaded
            self._ready = True

    def save(
        self,
        record: CustomerCommercialPendingExposureContainmentIssuanceRecord,
    ) -> CustomerCommercialPendingExposureContainmentIssuanceRecord:
        if not isinstance(
            record,
            CustomerCommercialPendingExposureContainmentIssuanceRecord,
        ):
            raise TypeError(
                "save requires containment issuance record."
            )

        self._validate_record(
            record
        )

        with self._lock:
            self._require_ready()

            replay_key = self._replay_key(
                trigger_id=record.trigger_id,
                symbol=record.symbol,
            )

            existing = self._records.get(
                replay_key
            )

            if existing is not None:
                if existing != record:
                    raise ValueError(
                        "Containment issuance replay conflict."
                    )

                return existing

            for stored in self._records.values():
                if (
                    stored.mission_id
                    == record.mission_id
                ):
                    raise ValueError(
                        "Containment mission_id already belongs "
                        "to another issuance."
                    )

            projected = dict(
                self._records
            )

            projected[
                replay_key
            ] = record

            self._persist(
                projected
            )

            self._records = projected

            return record

    def get_by_trigger_and_symbol(
        self,
        *,
        trigger_id: str,
        symbol: str,
    ) -> (
        CustomerCommercialPendingExposureContainmentIssuanceRecord
        | None
    ):
        normalized_trigger = self._normalize_string(
            "trigger_id",
            trigger_id,
        )

        normalized_symbol = self._normalize_string(
            "symbol",
            symbol,
        )

        with self._lock:
            self._require_ready()

            return self._records.get(
                self._replay_key(
                    trigger_id=normalized_trigger,
                    symbol=normalized_symbol,
                )
            )

    def get_by_mission_id(
        self,
        mission_id: str,
    ) -> (
        CustomerCommercialPendingExposureContainmentIssuanceRecord
        | None
    ):
        normalized = self._normalize_string(
            "mission_id",
            mission_id,
        )

        with self._lock:
            self._require_ready()

            matches = [
                record
                for record
                in self._records.values()
                if record.mission_id == normalized
            ]

            if len(matches) > 1:
                raise RuntimeError(
                    "Containment mission_id is not unique."
                )

            if not matches:
                return None

            return matches[0]

    @staticmethod
    def _replay_key(
        *,
        trigger_id: str,
        symbol: str,
    ) -> tuple[str, str]:
        return (
            trigger_id,
            symbol,
        )

    @classmethod
    def _validate_record(
        cls,
        record: CustomerCommercialPendingExposureContainmentIssuanceRecord,
    ) -> None:
        for name in (
            "issuance_id",
            "trigger_id",
            "deployment_id",
            "commercial_entitlement_id",
            "cycle_id",
            "agent_id",
            "account_fingerprint",
            "symbol",
            "mission_id",
            "created_at",
            "expires_at",
        ):
            cls._normalize_string(
                name,
                getattr(
                    record,
                    name,
                ),
            )

        for name in (
            "requested_by_sender_id",
            "sequence",
        ):
            value = getattr(
                record,
                name,
            )

            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value <= 0
            ):
                raise ValueError(
                    f"{name} must be positive int."
                )

    @staticmethod
    def _normalize_string(
        name: str,
        value: str,
    ) -> str:
        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"{name} is required."
            )

        normalized = value.strip()

        if normalized != value:
            raise ValueError(
                f"{name} must already be normalized."
            )

        return normalized

    @classmethod
    def _decode_record(
        cls,
        raw: object,
    ) -> CustomerCommercialPendingExposureContainmentIssuanceRecord:
        if not isinstance(raw, dict):
            raise RuntimeError(
                "Containment issuance record must be object."
            )

        try:
            record = (
                CustomerCommercialPendingExposureContainmentIssuanceRecord(
                    issuance_id=raw["issuance_id"],
                    trigger_id=raw["trigger_id"],
                    deployment_id=raw["deployment_id"],
                    commercial_entitlement_id=(
                        raw["commercial_entitlement_id"]
                    ),
                    cycle_id=raw["cycle_id"],
                    agent_id=raw["agent_id"],
                    account_fingerprint=(
                        raw["account_fingerprint"]
                    ),
                    symbol=raw["symbol"],
                    mission_id=raw["mission_id"],
                    requested_by_sender_id=(
                        raw["requested_by_sender_id"]
                    ),
                    created_at=raw["created_at"],
                    expires_at=raw["expires_at"],
                    sequence=raw["sequence"],
                )
            )
        except (
            KeyError,
            TypeError,
        ) as error:
            raise RuntimeError(
                "Invalid containment issuance record."
            ) from error

        try:
            cls._validate_record(
                record
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise RuntimeError(
                "Invalid containment issuance record."
            ) from error

        return record

    def _persist(
        self,
        records: dict[
            tuple[str, str],
            CustomerCommercialPendingExposureContainmentIssuanceRecord,
        ],
    ) -> None:
        encoded = (
            json.dumps(
                {
                    "version": STORE_VERSION,
                    "records": [
                        asdict(record)
                        for _, record
                        in sorted(
                            records.items()
                        )
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = self._path.with_name(
            f"{self._path.name}.tmp"
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
                self._path,
            )
        except OSError as error:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise RuntimeError(
                "Containment issuance store "
                "could not be persisted."
            ) from error

    def _require_ready(
        self,
    ) -> None:
        if not self._ready:
            raise RuntimeError(
                "Containment issuance store "
                "is not initialized."
            )
