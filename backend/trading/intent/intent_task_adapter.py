"""
TODOBA Intent Task Adapter

Converts TradingIntent into TODOBA organizational Task.
"""

from backend.task.task_factory import TaskFactory
from backend.trading.intent.trading_intent import TradingIntent


class IntentTaskAdapter:

    def to_task(self, intent: TradingIntent):

        return TaskFactory.create(
            task_type="trade",
            payload=intent,
        )