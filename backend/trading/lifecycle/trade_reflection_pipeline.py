"""
TODOBA Trade Reflection Pipeline

Transforms a closed-trade observation into meaningful
organizational memory.

Architecture:

ClosedTradeObservation
        ↓
TradeOutcomeEvaluator
        ↓
TradeExperienceBuilder
        ↓
TradeMemoryBridge
        ↓
Canonical Brain Experience
        ↓
MemoryEngine
"""

from dataclasses import dataclass
from typing import Optional

from backend.brain.models.experience import Experience
from backend.trading.lifecycle.closed_trade_observation import (
    ClosedTradeObservation,
)
from backend.trading.lifecycle.trade_experience import (
    TradeExperience,
)
from backend.trading.lifecycle.trade_experience_builder import (
    TradeExperienceBuilder,
)
from backend.trading.lifecycle.trade_memory_bridge import (
    TradeMemoryBridge,
)
from backend.trading.lifecycle.trade_outcome_evaluator import (
    TradeOutcomeEvaluation,
    TradeOutcomeEvaluator,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)
from backend.trading.lifecycle.trade_status import (
    TradeStatus,
)


@dataclass(frozen=True)
class TradeReflectionResult:
    """
    Complete result of reflecting on one closed trade.
    """

    observation: ClosedTradeObservation
    evaluation: TradeOutcomeEvaluation
    trade_experience: TradeExperience
    memory_experience: Experience


class TradeReflectionPipeline:
    """
    Interpret and preserve one completed trade.

    This pipeline requires both:

    - TradeRecord: TODOBA's internal trading identity.
    - ClosedTradeObservation: broker evidence of closure.
    """

    def __init__(
        self,
        *,
        memory_bridge: TradeMemoryBridge,
        evaluator: Optional[
            TradeOutcomeEvaluator
        ] = None,
        experience_builder: Optional[
            TradeExperienceBuilder
        ] = None,
    ):
        if not isinstance(
            memory_bridge,
            TradeMemoryBridge,
        ):
            raise TypeError(
                "TradeReflectionPipeline requires "
                "TradeMemoryBridge."
            )

        self.memory_bridge = memory_bridge

        self.evaluator = (
            evaluator
            if evaluator is not None
            else TradeOutcomeEvaluator()
        )

        self.experience_builder = (
            experience_builder
            if experience_builder is not None
            else TradeExperienceBuilder()
        )

    def reflect(
        self,
        *,
        trade_record: TradeRecord,
        observation: ClosedTradeObservation,
        context: Optional[dict] = None,
    ) -> TradeReflectionResult:
        """
        Evaluate a closed trade and preserve its meaning.
        """

        if not isinstance(
            trade_record,
            TradeRecord,
        ):
            raise TypeError(
                "reflect requires TradeRecord."
            )

        if not isinstance(
            observation,
            ClosedTradeObservation,
        ):
            raise TypeError(
                "reflect requires "
                "ClosedTradeObservation."
            )

        if trade_record.status != TradeStatus.CLOSED:
            raise ValueError(
                "TradeRecord must be CLOSED "
                "before reflection."
            )

        evaluation = self.evaluator.evaluate(
            observation
        )

        trade_experience = (
            self.experience_builder.build(
                trade_record=trade_record,
                outcome=evaluation.outcome,
                reason=evaluation.reason,
            )
        )

        memory_context = {
            "position_id": observation.position_id,
            "close_deal_id": (
                observation.close_deal_id
            ),
            "order_id": observation.order_id,
            "symbol": observation.symbol,
            "action": observation.action,
            "volume": observation.volume,
            "close_price": observation.close_price,
            "closed_at": (
                observation.closed_at.isoformat()
            ),
            "gross_profit": (
                observation.gross_profit
            ),
            "commission": observation.commission,
            "swap": observation.swap,
            "fee": observation.fee,
            "net_profit": observation.net_profit,
            "close_reason": (
                observation.close_reason
            ),
            "broker_comment": observation.comment,
        }

        if context:
            memory_context.update(context)

        memory_experience = (
            self.memory_bridge.remember_trade_outcome(
                trade_experience,
                context=memory_context,
            )
        )

        return TradeReflectionResult(
            observation=observation,
            evaluation=evaluation,
            trade_experience=trade_experience,
            memory_experience=memory_experience,
        )
