"""
TODOBA Trade Task Remote Execution Bridge

Converts an approved trade Task into an ExecutionMission
and submits it through the existing ExecutionMissionService.

This component does not:

- execute broker orders
- own mission storage
- own delivery queues
- make trading decisions
- access MT5
"""

from backend.task.task import Task
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_service import (
    ExecutionMissionService,
)
from backend.trading.execution.trade_task_execution_mission_adapter import (
    TradeTaskExecutionMissionAdapter,
)


class TradeTaskRemoteExecutionBridge:
    """
    Dispatch approved trade Tasks through remote execution.
    """

    def __init__(
        self,
        *,
        mission_service: ExecutionMissionService,
    ) -> None:
        if not isinstance(
            mission_service,
            ExecutionMissionService,
        ):
            raise TypeError(
                "TradeTaskRemoteExecutionBridge requires "
                "ExecutionMissionService."
            )

        self.mission_service = mission_service
        self.mission_adapter = (
            TradeTaskExecutionMissionAdapter()
        )

    def dispatch(
        self,
        task: Task,
        *,
        mission_id: str,
        agent_id: str,
        account_fingerprint: str,
        volume: float,
        magic_number: int,
        comment: str,
        created_at: str,
        expires_at: str,
        sequence: int,
    ) -> ExecutionMission:
        mission = self.mission_adapter.to_mission(
            task,
            mission_id=mission_id,
            agent_id=agent_id,
            account_fingerprint=(
                account_fingerprint
            ),
            volume=volume,
            magic_number=magic_number,
            comment=comment,
            created_at=created_at,
            expires_at=expires_at,
            sequence=sequence,
        )

        return self.mission_service.create_mission(
            mission
        )