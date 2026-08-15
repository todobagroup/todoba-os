"""
TODOBA Control Mission Lifecycle API

Receives lifecycle evidence from Trusted Agents for remote
control missions.

This API owns HTTP transport and Agent ownership checks.
Lifecycle transitions and persistence belong to
ControlMissionLifecycleService.
"""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from pydantic import Field

from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


NonNegativeInt = Annotated[
    int,
    Field(
        strict=True,
        ge=0,
    ),
]


class ControlMissionAcknowledgementRequest(BaseModel):
    mission_id: str
    agent_id: str
    acknowledged_at: str


class ControlMissionExecutionStartedRequest(BaseModel):
    mission_id: str
    agent_id: str
    started_at: str


class ControlMissionCompletedRequest(BaseModel):
    mission_id: str
    agent_id: str
    completed_at: str

    matched_position_count: NonNegativeInt
    closed_position_count: NonNegativeInt
    matched_pending_order_count: NonNegativeInt
    canceled_pending_order_count: NonNegativeInt


class ControlMissionFailedRequest(BaseModel):
    mission_id: str
    agent_id: str
    failed_at: str
    failure_reason: str = Field(
        min_length=1
    )

    matched_position_count: NonNegativeInt = 0
    closed_position_count: NonNegativeInt = 0
    matched_pending_order_count: NonNegativeInt = 0
    canceled_pending_order_count: NonNegativeInt = 0
    failed_item_count: NonNegativeInt = 0


def _require_owned_mission(
    *,
    lifecycle_service: ControlMissionLifecycleService,
    mission_id: str,
    evidence_agent_id: str,
    authenticated_agent_id: str,
) -> None:
    if evidence_agent_id != authenticated_agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Control mission evidence does not belong "
                "to authenticated Agent."
            ),
        )

    record = lifecycle_service.registry.get(
        mission_id
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Control mission record not found.",
        )

    if record.mission.agent_id != authenticated_agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Control mission does not belong to "
                "authenticated Agent."
            ),
        )


def _raise_lifecycle_conflict(
    error: Exception,
) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(
            error
        ),
    ) from error


def create_control_mission_lifecycle_router(
    lifecycle_service: ControlMissionLifecycleService,
    authenticator: TrustedAgentAuthenticator,
) -> APIRouter:
    if not isinstance(
        lifecycle_service,
        ControlMissionLifecycleService,
    ):
        raise TypeError(
            "create_control_mission_lifecycle_router "
            "requires ControlMissionLifecycleService."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_control_mission_lifecycle_router "
            "requires TrustedAgentAuthenticator."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/control/missions/acknowledge"
    )
    def acknowledge_control_mission(
        request: ControlMissionAcknowledgementRequest,
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        _require_owned_mission(
            lifecycle_service=lifecycle_service,
            mission_id=request.mission_id,
            evidence_agent_id=request.agent_id,
            authenticated_agent_id=(
                authenticated_agent_id
            ),
        )

        try:
            lifecycle_service.acknowledge(
                request.mission_id,
                request.acknowledged_at,
            )
        except (TypeError, ValueError) as error:
            _raise_lifecycle_conflict(
                error
            )

        return {
            "status": "acknowledged",
            "mission_id": request.mission_id,
        }

    @router.post(
        "/control/missions/execution-started"
    )
    def start_control_mission_execution(
        request: ControlMissionExecutionStartedRequest,
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        _require_owned_mission(
            lifecycle_service=lifecycle_service,
            mission_id=request.mission_id,
            evidence_agent_id=request.agent_id,
            authenticated_agent_id=(
                authenticated_agent_id
            ),
        )

        try:
            lifecycle_service.start_execution(
                request.mission_id,
                request.started_at,
            )
        except (TypeError, ValueError) as error:
            _raise_lifecycle_conflict(
                error
            )

        return {
            "status": "executing",
            "mission_id": request.mission_id,
        }

    @router.post(
        "/control/missions/completed"
    )
    def complete_control_mission(
        request: ControlMissionCompletedRequest,
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        _require_owned_mission(
            lifecycle_service=lifecycle_service,
            mission_id=request.mission_id,
            evidence_agent_id=request.agent_id,
            authenticated_agent_id=(
                authenticated_agent_id
            ),
        )

        try:
            lifecycle_service.complete_execution(
                request.mission_id,
                request.completed_at,
                matched_position_count=(
                    request.matched_position_count
                ),
                closed_position_count=(
                    request.closed_position_count
                ),
                matched_pending_order_count=(
                    request.matched_pending_order_count
                ),
                canceled_pending_order_count=(
                    request.canceled_pending_order_count
                ),
            )
        except (TypeError, ValueError) as error:
            _raise_lifecycle_conflict(
                error
            )

        return {
            "status": "completed",
            "mission_id": request.mission_id,
        }

    @router.post(
        "/control/missions/failed"
    )
    def fail_control_mission(
        request: ControlMissionFailedRequest,
        authenticated_agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        _require_owned_mission(
            lifecycle_service=lifecycle_service,
            mission_id=request.mission_id,
            evidence_agent_id=request.agent_id,
            authenticated_agent_id=(
                authenticated_agent_id
            ),
        )

        try:
            lifecycle_service.fail_execution(
                request.mission_id,
                request.failed_at,
                request.failure_reason,
                matched_position_count=(
                    request.matched_position_count
                ),
                closed_position_count=(
                    request.closed_position_count
                ),
                matched_pending_order_count=(
                    request.matched_pending_order_count
                ),
                canceled_pending_order_count=(
                    request.canceled_pending_order_count
                ),
                failed_item_count=(
                    request.failed_item_count
                ),
            )
        except (TypeError, ValueError) as error:
            _raise_lifecycle_conflict(
                error
            )

        return {
            "status": "failed",
            "mission_id": request.mission_id,
        }

    return router