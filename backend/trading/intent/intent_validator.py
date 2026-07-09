"""
TODOBA Intent Validator
"""

from backend.trading.intent.trading_intent import TradingIntent


class IntentValidator:

    def validate(self, intent: TradingIntent):

        if intent.action not in ("BUY", "SELL"):

            raise ValueError("Unsupported action.")

        if not intent.asset:

            raise ValueError("Asset is required.")

        return True