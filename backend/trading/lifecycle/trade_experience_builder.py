"""
TODOBA Trade Experience Builder
"""

from backend.trading.lifecycle.trade_experience import TradeExperience


class TradeExperienceBuilder:

    def build(
        self,
        *,
        trade_record,
        outcome,
        reason,
    ):

        return TradeExperience(
            trade_id=trade_record.trade_id,
            outcome=outcome,
            reason=reason,
        )