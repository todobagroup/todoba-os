"""
TODOBA Execution Mission Bridge

Consumes ExecutionMission objects and sends them
into the organizational Trading flow.

Flow:

ExecutionMission
        ->
TradingIntent
        ->
Task
        ->
TradingDepartment

This component does not:
- execute broker orders
- manage MT5
- own TradingRuntime
"""

from typing import Optional

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.execution_mission_intent_adapter import (
    ExecutionMissionIntentAdapter,
)
from backend.trading.intent.intent_task_adapter import (
    IntentTaskAdapter,
)
from backend.trading.department.trading_department import (
    TradingDepartment,
)


class ExecutionMissionBridge:
    """
    Bridge between remote execution missions and
    TODOBA Trading organization.
    """

    def __init__(
        self,
        *,
        store: ExecutionMissionStore,
        department: TradingDepartment,
    ) -> None:

        if not isinstance(
            store,
            ExecutionMissionStore,
        ):
            raise TypeError(
                "ExecutionMissionBridge requires "
                "ExecutionMissionStore."
            )

        if not isinstance(
            department,
            TradingDepartment,
        ):
            raise TypeError(
                "ExecutionMissionBridge requires "
                "TradingDepartment."
            )

        self.store = store
        self.department = department

        self.mission_adapter = (
            ExecutionMissionIntentAdapter()
        )

        self.task_adapter = (
            IntentTaskAdapter()
        )

    def dispatch_next(
        self,
    ) -> Optional[object]:
        """
        Consume one mission and dispatch it
        into TradingDepartment.
        """

        mission = self.store.pop()

        if mission is None:
            return None

        intent = (
            self.mission_adapter
            .to_intent(mission)
        )

        task = (
            self.task_adapter
            .to_task(intent)
        )

        return self.department.runtime.dispatch(
            task
        )