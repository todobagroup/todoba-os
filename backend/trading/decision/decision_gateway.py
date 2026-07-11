"""
TODOBA Decision Gateway

Stops rejected intents before Task creation.
"""

from backend.trading.decision.decision_engine import TradingDecisionEngine
from backend.trading.intent.intent_task_adapter import IntentTaskAdapter


class DecisionGateway:

    def __init__(self):

        self.engine = TradingDecisionEngine()
        self.adapter = IntentTaskAdapter()

    def create_task_if_approved(
        self,
        *,
        intent,
        has_open_position,
        spread_ok,
        market_open,
        risk_ok,
    ):

        decision = self.engine.decide(
            has_open_position=has_open_position,
            spread_ok=spread_ok,
            market_open=market_open,
            risk_ok=risk_ok,
        )

        if not decision.approved:
            return None, decision

        task = self.adapter.to_task(intent)

        return task, decision