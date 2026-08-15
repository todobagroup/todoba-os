"""
TODOBA Control Mission API

Exposes the authenticated remote control mission polling
boundary consumed by Trusted Agents.

This module owns HTTP transport only. Mission storage,
delivery leasing, lifecycle tracking, expiration policy,
serialization, signing, and authentication remain separate
capabilities.
"""

from datetime import datetime
from datetime import timezone

from fastapi import APIRouter
from fastapi import Depends

from backend.trading.control.control_mission_delivery_expiration_policy import (
    ControlMissionDeliveryExpirationPolicy,
)
from backend.trading.control.control_mission_delivery_lease_service import (
    ControlMissionDeliveryLeaseService,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
)
from backend.trading.control.control_mission_serializer import (
    ControlMissionSerializer,
)
from backend.trading.control.control_mission_signer import (
    ControlMissionSigner,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


def _serialize_utc(
    value: datetime,
) -> str:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "clock must return datetime."
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            "clock must return timezone-aware datetime."
        )

    return (
        value.astimezone(
            timezone.utc
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def create_control_mission_router(
    store: ControlMissionStore,
    authenticator: TrustedAgentAuthenticator,
    lease_service: ControlMissionDeliveryLeaseService,
    lifecycle_service: ControlMissionLifecycleService,
    expiration_policy: ControlMissionDeliveryExpirationPolicy,
    signer: ControlMissionSigner,
) -> APIRouter:
    if not isinstance(
        store,
        ControlMissionStore,
    ):
        raise TypeError(
            "create_control_mission_router requires "
            "ControlMissionStore."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_control_mission_router requires "
            "TrustedAgentAuthenticator."
        )

    if not isinstance(
        lease_service,
        ControlMissionDeliveryLeaseService,
    ):
        raise TypeError(
            "lease_service must be "
            "ControlMissionDeliveryLeaseService."
        )

    if not isinstance(
        lifecycle_service,
        ControlMissionLifecycleService,
    ):
        raise TypeError(
            "lifecycle_service must be "
            "ControlMissionLifecycleService."
        )

    if not isinstance(
        expiration_policy,
        ControlMissionDeliveryExpirationPolicy,
    ):
        raise TypeError(
            "expiration_policy must be "
            "ControlMissionDeliveryExpirationPolicy."
        )

    if not isinstance(
        signer,
        ControlMissionSigner,
    ):
        raise TypeError(
            "signer must be ControlMissionSigner."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.get(
        "/control/missions/next"
    )
    def next_control_mission(
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        mission = store.pop_for_agent(
            authenticated_agent_id
        )

        if mission is None:
            return {
                "status": "empty",
                "mission": None,
            }

        expired = False

        try:
            current_time = lease_service.clock()
            current_time_utc = _serialize_utc(
                current_time
            )

            expired = expiration_policy.is_expired(
                mission,
                current_time,
            )

            if expired:
                lifecycle_service.fail_execution(
                    mission_id=mission.mission_id,
                    failed_at=current_time_utc,
                    failure_reason=(
                        "Control mission expired "
                        "before delivery."
                    ),
                )

                return {
                    "status": "empty",
                    "mission": None,
                }

            lease = lease_service.acquire(
                mission_id=mission.mission_id,
                agent_id=authenticated_agent_id,
            )

            lifecycle_service.mark_delivered(
                mission_id=mission.mission_id,
                delivered_at=lease.leased_at,
            )

            payload = ControlMissionSerializer.serialize(
                mission
            )

            response = {
                "status": "available",
                "mission": payload,
                "agent_id": authenticated_agent_id,
                **payload,
                "mission_signature": signer.sign(
                    mission
                ),
                "delivery_lease": {
                    "mission_id": lease.mission_id,
                    "agent_id": lease.agent_id,
                    "leased_at": lease.leased_at,
                    "expires_at": lease.expires_at,
                },
            }

            return response

        except Exception:
            if not expired:
                store.redeliver(
                    mission
                )
            raise

    return router