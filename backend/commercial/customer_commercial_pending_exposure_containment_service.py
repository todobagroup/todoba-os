"""
TODOBA Customer Commercial Pending Exposure Containment Service.

Issues durable CANCEL_ALL_PENDING control missions when an
authoritative commercial capacity decision requires upgrade.

Responsibilities:
- require authoritative UPGRADE_REQUIRED capacity status
- resolve authoritative deployment identity
- issue one control mission per production control symbol
- freeze issuance facts durably before mission submission
- reuse exact frozen issuance facts on retry
- delegate persistence, replay security, lifecycle, and delivery
  to the existing ControlMissionService

This component does not:
- cancel MT5 orders directly
- close existing positions
- mutate pending-order execution state
- claim broker cancellation success
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Callable

from backend.commercial.customer_commercial_capacity_decision_service import (
    CustomerCommercialCapacityDecisionStatus,
)
from backend.commercial.customer_commercial_pending_exposure_containment_issuance import (
    CustomerCommercialPendingExposureContainmentIssuanceRecord,
)
from backend.trading.control.control_action import (
    ControlAction,
)
from backend.trading.control.control_mission import (
    ControlMission,
)
from backend.trading.control.control_mission_issuance_scope import (
    INTERNAL_COMMERCIAL_CONTROL_SENDER_ID,
    PRODUCTION_CONTROL_ALLOWED_SYMBOLS,
    TODOBA_MAGIC_NUMBER,
)


class CustomerCommercialPendingExposureContainmentService:
    """
    Issue durable commercial pending-exposure containment missions.
    """

    _MISSION_TTL = timedelta(minutes=2)

    def __init__(
        self,
        *,
        deployment_binding_store,
        capacity_decision_provider,
        issuance_store,
        control_mission_service,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._deployment_binding_store = (
            deployment_binding_store
        )
        self._capacity_decision_provider = (
            capacity_decision_provider
        )
        self._issuance_store = issuance_store
        self._control_mission_service = (
            control_mission_service
        )
        self._now_provider = (
            datetime.now
            if now_provider is None
            else now_provider
        )

    def issue(
        self,
        *,
        trigger_id: str,
        deployment_id: str,
    ) -> tuple[ControlMission, ...]:
        normalized_trigger_id = (
            self._normalize_required_string(
                "trigger_id",
                trigger_id,
            )
        )
        normalized_deployment_id = (
            self._normalize_required_string(
                "deployment_id",
                deployment_id,
            )
        )

        decision = (
            self._capacity_decision_provider.provide(
                deployment_id=(
                    normalized_deployment_id
                )
            )
        )

        if (
            decision.status
            != CustomerCommercialCapacityDecisionStatus.UPGRADE_REQUIRED
        ):
            raise RuntimeError(
                "Pending exposure containment requires "
                "UPGRADE_REQUIRED capacity decision."
            )

        binding = (
            self._deployment_binding_store.get_by_deployment_id(
                deployment_id=(
                    normalized_deployment_id
                )
            )
        )

        if binding is None:
            raise RuntimeError(
                "Unknown commercial deployment."
            )

        self._validate_authoritative_identity(
            deployment_id=normalized_deployment_id,
            decision=decision,
            binding=binding,
        )

        symbols = self._normalized_symbols()

        missions: list[ControlMission] = []

        for symbol in symbols:
            issuance = (
                self._issuance_store
                .get_by_trigger_and_symbol(
                    trigger_id=normalized_trigger_id,
                    symbol=symbol,
                )
            )

            if issuance is None:
                issuance = self._freeze_new_issuance(
                    trigger_id=normalized_trigger_id,
                    symbol=symbol,
                    decision=decision,
                    binding=binding,
                )

                issuance = self._issuance_store.save(
                    issuance
                )
            else:
                self._validate_replayed_issuance(
                    issuance=issuance,
                    decision=decision,
                    binding=binding,
                    trigger_id=normalized_trigger_id,
                    symbol=symbol,
                )

            mission = self._mission_from_issuance(
                issuance
            )

            created = (
                self._control_mission_service
                .create_mission(
                    mission
                )
            )

            missions.append(created)

        return tuple(missions)

    def _freeze_new_issuance(
        self,
        *,
        trigger_id: str,
        symbol: str,
        decision,
        binding,
    ) -> (
        CustomerCommercialPendingExposureContainmentIssuanceRecord
    ):
        created_at = self._normalized_now()
        expires_at = created_at + self._MISSION_TTL

        issuance_id = (
            "commercial-containment-issuance-"
            f"{uuid.uuid4().hex}"
        )

        mission_id = (
            "commercial-containment-"
            f"{uuid.uuid4().hex}"
        )

        sequence = (
            self._source_sequence_from_mission_id(
                mission_id
            )
        )

        return (
            CustomerCommercialPendingExposureContainmentIssuanceRecord(
                issuance_id=issuance_id,
                trigger_id=trigger_id,
                deployment_id=binding.deployment_id,
                commercial_entitlement_id=(
                    binding.commercial_entitlement_id
                ),
                cycle_id=decision.cycle_id,
                agent_id=binding.agent_id,
                account_fingerprint=(
                    binding.account_fingerprint
                ),
                symbol=symbol,
                mission_id=mission_id,
                requested_by_sender_id=(
                    INTERNAL_COMMERCIAL_CONTROL_SENDER_ID
                ),
                created_at=self._serialize_utc(
                    created_at
                ),
                expires_at=self._serialize_utc(
                    expires_at
                ),
                sequence=sequence,
            )
        )

    @staticmethod
    def _mission_from_issuance(
        issuance,
    ) -> ControlMission:
        return ControlMission(
            mission_id=issuance.mission_id,
            agent_id=issuance.agent_id,
            account_fingerprint=(
                issuance.account_fingerprint
            ),
            action=ControlAction.CANCEL_ALL_PENDING,
            symbol=issuance.symbol,
            magic_number=TODOBA_MAGIC_NUMBER,
            requested_by_sender_id=(
                issuance.requested_by_sender_id
            ),
            created_at=issuance.created_at,
            expires_at=issuance.expires_at,
            sequence=issuance.sequence,
        )

    @staticmethod
    def _validate_authoritative_identity(
        *,
        deployment_id: str,
        decision,
        binding,
    ) -> None:
        if decision.deployment_id != deployment_id:
            raise RuntimeError(
                "Commercial capacity decision identity "
                "does not match deployment binding."
            )

        if binding.deployment_id != deployment_id:
            raise RuntimeError(
                "Commercial deployment binding identity "
                "does not match requested deployment."
            )

        if (
            decision.commercial_entitlement_id
            != binding.commercial_entitlement_id
        ):
            raise RuntimeError(
                "Commercial decision/binding identity mismatch."
            )

    @staticmethod
    def _validate_replayed_issuance(
        *,
        issuance,
        decision,
        binding,
        trigger_id: str,
        symbol: str,
    ) -> None:
        expected = (
            issuance.trigger_id == trigger_id
            and issuance.symbol == symbol
            and issuance.deployment_id
            == binding.deployment_id
            and issuance.commercial_entitlement_id
            == binding.commercial_entitlement_id
            and issuance.cycle_id
            == decision.cycle_id
            and issuance.agent_id
            == binding.agent_id
            and issuance.account_fingerprint
            == binding.account_fingerprint
            and issuance.requested_by_sender_id
            == INTERNAL_COMMERCIAL_CONTROL_SENDER_ID
        )

        if not expected:
            raise RuntimeError(
                "Frozen containment issuance identity conflict."
            )

    def _normalized_now(self) -> datetime:
        now = self._now_provider()

        if not isinstance(now, datetime):
            raise TypeError(
                "now_provider must return datetime."
            )

        if now.tzinfo is None:
            raise ValueError(
                "now_provider must return timezone-aware datetime."
            )

        return now.astimezone(UTC)

    @staticmethod
    def _serialize_utc(
        value: datetime,
    ) -> str:
        return (
            value.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @staticmethod
    def _source_sequence_from_mission_id(
        mission_id: str,
    ) -> int:
        digest = hashlib.sha256(
            mission_id.encode("utf-8")
        ).digest()

        value = int.from_bytes(
            digest[:8],
            byteorder="big",
            signed=False,
        )

        value &= (1 << 63) - 1

        return value or 1

    @staticmethod
    def _normalized_symbols() -> tuple[str, ...]:
        result: list[str] = []

        for raw_symbol in (
            PRODUCTION_CONTROL_ALLOWED_SYMBOLS
        ):
            if not isinstance(raw_symbol, str):
                raise RuntimeError(
                    "Production control symbol is invalid."
                )

            symbol = raw_symbol.strip()

            if not symbol:
                raise RuntimeError(
                    "Production control symbol is invalid."
                )

            if symbol not in result:
                result.append(symbol)

        if not result:
            raise RuntimeError(
                "Production control symbol scope is empty."
            )

        return tuple(result)

    @staticmethod
    def _normalize_required_string(
        name: str,
        value: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} must not be empty."
            )

        return normalized
