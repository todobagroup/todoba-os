"""
TODOBA Execution Mission API

Exposes the remote mission polling boundary.

This module owns HTTP transport only.
Mission storage, delivery leasing, lifecycle tracking,
delivery expiration policy, serialization, signing,
protocol negotiation, and authentication policy belong
to separate capabilities.
"""

from typing import Optional

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from backend.trading.execution.execution_mission_delivery_expiration_policy import (
    ExecutionMissionDeliveryExpirationPolicy,
)
from backend.trading.execution.execution_mission_delivery_lease_service import (
    ExecutionMissionDeliveryLeaseService,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)
from backend.trading.execution.execution_mission_serializer import (
    ExecutionMissionSerializer,
)
from backend.trading.execution.execution_mission_serializer_v2 import (
    ExecutionMissionSerializerV2,
)
from backend.trading.execution.execution_mission_signer import (
    ExecutionMissionSigner,
)
from backend.trading.execution.execution_mission_signer_v2 import (
    ExecutionMissionSignerV2,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)
from backend.trading.execution.trusted_agent_protocol_dependency import (
    TrustedAgentProtocolContext,
    create_trusted_agent_protocol_dependency,
)


def create_execution_mission_router(
    store: ExecutionMissionStore,
    authenticator: TrustedAgentAuthenticator,
    lease_service: Optional[
        ExecutionMissionDeliveryLeaseService
    ] = None,
    lifecycle_service: Optional[
        ExecutionMissionLifecycleService
    ] = None,
    expiration_policy: Optional[
        ExecutionMissionDeliveryExpirationPolicy
    ] = None,
    signer: Optional[
        ExecutionMissionSigner
    ] = None,
    *,
    signer_v2: Optional[
        ExecutionMissionSignerV2
    ] = None,
) -> APIRouter:
    if not isinstance(
        store,
        ExecutionMissionStore,
    ):
        raise TypeError(
            "create_execution_mission_router requires "
            "ExecutionMissionStore."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_execution_mission_router requires "
            "TrustedAgentAuthenticator."
        )

    if (
        lease_service is not None
        and not isinstance(
            lease_service,
            ExecutionMissionDeliveryLeaseService,
        )
    ):
        raise TypeError(
            "lease_service must be "
            "ExecutionMissionDeliveryLeaseService."
        )

    if (
        lifecycle_service is not None
        and not isinstance(
            lifecycle_service,
            ExecutionMissionLifecycleService,
        )
    ):
        raise TypeError(
            "lifecycle_service must be "
            "ExecutionMissionLifecycleService."
        )

    if (
        expiration_policy is not None
        and not isinstance(
            expiration_policy,
            ExecutionMissionDeliveryExpirationPolicy,
        )
    ):
        raise TypeError(
            "expiration_policy must be "
            "ExecutionMissionDeliveryExpirationPolicy."
        )

    if (
        signer is not None
        and not isinstance(
            signer,
            ExecutionMissionSigner,
        )
    ):
        raise TypeError(
            "signer must be ExecutionMissionSigner."
        )

    if (
        signer_v2 is not None
        and not isinstance(
            signer_v2,
            ExecutionMissionSignerV2,
        )
    ):
        raise TypeError(
            "signer_v2 must be ExecutionMissionSignerV2."
        )

    require_trusted_agent_protocol = (
        create_trusted_agent_protocol_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.get(
        "/missions/next",
    )
    def next_mission(
        agent_context: TrustedAgentProtocolContext = Depends(
            require_trusted_agent_protocol
        ),
    ):
        authenticated_agent_id = (
            agent_context.agent_id
        )

        mission_protocol = (
            agent_context.mission_protocol
        )

        if (
            mission_protocol == "V2"
            and signer_v2 is None
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail=(
                    "TODOBA mission protocol V2 "
                    "is not enabled."
                ),
            )

        mission = store.pop_for_agent(
            authenticated_agent_id
        )

        if mission is None:
            return {
                "status": "empty",
                "mission": None,
            }

        if (
            expiration_policy is not None
            and lease_service is not None
        ):
            current_time = lease_service.clock()

            if expiration_policy.is_expired(
                mission,
                current_time,
            ):
                if lifecycle_service is not None:
                    lifecycle_service.fail_execution(
                        mission_id=mission.mission_id,
                        failed_at=(
                            lease_service._serialize_utc(
                                current_time
                            )
                        ),
                        failure_reason=(
                            "Execution mission expired "
                            "before delivery."
                        ),
                    )

                return {
                    "status": "empty",
                    "mission": None,
                }

        lease = None

        if lease_service is not None:
            lease = lease_service.acquire(
                mission_id=mission.mission_id,
                agent_id=authenticated_agent_id,
            )

        if (
            lifecycle_service is not None
            and lease is not None
        ):
            lifecycle_service.mark_delivered(
                mission_id=mission.mission_id,
                delivered_at=lease.leased_at,
            )

        if mission_protocol == "V2":
            payload = (
                ExecutionMissionSerializerV2.serialize(
                    mission
                )
            )
        else:
            payload = (
                ExecutionMissionSerializer.serialize(
                    mission
                )
            )

        response = {
            "status": "available",
            "mission": payload,
            "agent_id": authenticated_agent_id,
            **payload,
        }

        if mission_protocol == "V2":
            response["mission_signature"] = (
                signer_v2.sign(
                    mission
                )
            )
        elif signer is not None:
            response["mission_signature"] = (
                signer.sign(
                    mission
                )
            )

        if lease is not None:
            response["delivery_lease"] = {
                "mission_id": lease.mission_id,
                "agent_id": lease.agent_id,
                "leased_at": lease.leased_at,
                "expires_at": lease.expires_at,
            }

        return response

    return router