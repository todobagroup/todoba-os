"""
TODOBA Trade Task Execution Mission Adapter

Converts an approved trade Task into
an ExecutionMission.

This component does not:

- execute broker orders
- deliver missions
- own mission persistence
- calculate trading decisions
"""

from backend.task.task import Task
from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.intent.trading_intent import (
    TradingIntent,
)


class TradeTaskExecutionMissionAdapter:
    """
    Convert approved trade Tasks into ExecutionMission objects.
    """

    def to_mission(
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
        if not isinstance(
            task,
            Task,
        ):
            raise TypeError(
                "TradeTaskExecutionMissionAdapter "
                "requires Task."
            )

        if task.task_type != "trade":
            raise ValueError(
                "Task must have task_type='trade'."
            )

        if not isinstance(
            task.payload,
            TradingIntent,
        ):
            raise TypeError(
                "Trade task payload must be "
                "TradingIntent."
            )

        intent = task.payload

        return ExecutionMission(
            mission_id=mission_id,
            agent_id=agent_id,
            account_fingerprint=(
                account_fingerprint
            ),
            symbol=intent.asset,
            order_type=intent.order_type,
            volume=volume,
            entry=intent.entry,
            sl=intent.sl,
            tp=intent.tp,
            magic_number=magic_number,
            comment=comment,
            created_at=created_at,
            expires_at=expires_at,
            sequence=sequence,
        )