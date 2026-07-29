"""
TODOBA Execution Mission Intent Adapter

Converts an approved ExecutionMission into
a TradingIntent for organizational execution.

This component does not:
- execute orders
- create tasks
- access brokers

It only translates mission data into trading intent.
"""

from backend.trading.execution.execution_mission import (
    ExecutionMission,
)
from backend.trading.intent.trading_intent import (
    TradingIntent,
)


class ExecutionMissionIntentAdapter:
    """
    Convert ExecutionMission into TradingIntent.
    """

    def to_intent(
        self,
        mission: ExecutionMission,
    ) -> TradingIntent:

        if not isinstance(
            mission,
            ExecutionMission,
        ):
            raise TypeError(
                "ExecutionMissionIntentAdapter requires "
                "ExecutionMission."
            )

        return TradingIntent(
            order_type=mission.order_type,
            asset=mission.symbol,
            entry=mission.entry,
            sl=mission.sl,
            tp=mission.tp,
        )