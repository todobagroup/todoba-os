"""
TODOBA Trade Memory Bridge

Converts trading lifecycle events into canonical Brain
Experience objects and preserves them in MemoryEngine.

Architecture:

TradeRecord / TradeExperience
        ↓
Canonical Brain Experience
        ↓
MemoryEngine

This bridge does not evaluate trading performance.
It only preserves the meaning already produced by
the trading lifecycle.
"""

import json
from typing import Optional

from backend.brain.memory import MemoryEngine
from backend.brain.models.experience import Experience
from backend.trading.lifecycle.trade_experience import (
    TradeExperience,
)
from backend.trading.lifecycle.trade_record import (
    TradeRecord,
)


class TradeMemoryBridge:
    """
    Preserve trading lifecycle meaning in TODOBA Memory.
    """

    def __init__(
        self,
        memory: MemoryEngine,
    ):
        if not isinstance(memory, MemoryEngine):
            raise TypeError(
                "TradeMemoryBridge requires MemoryEngine."
            )

        self.memory = memory

    def remember_open_trade(
        self,
        trade_record: TradeRecord,
        *,
        origin: str = "unknown",
        context: Optional[dict] = None,
    ) -> Experience:
        """
        Preserve the fact that a trade was successfully opened.
        """

        if not isinstance(
            trade_record,
            TradeRecord,
        ):
            raise TypeError(
                "remember_open_trade requires TradeRecord."
            )

        status_value = str(
            trade_record.status.value
        ).lower()

        meaning = {
            "event": "trade_opened",
            "trade_id": trade_record.trade_id,
            "origin": origin,
            "symbol": trade_record.symbol,
            "action": trade_record.action,
            "volume": trade_record.volume,
            "status": status_value,
            "order": trade_record.order,
            "deal": trade_record.deal,
            "context": context or {},
        }

        experience = Experience(
            source="trading",
            content=json.dumps(
                meaning,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

        self.memory.save(experience)

        return experience

    def remember_trade_outcome(
        self,
        trade_experience: TradeExperience,
        *,
        context: Optional[dict] = None,
    ) -> Experience:
        """
        Preserve the interpreted outcome of a completed trade.
        """

        if not isinstance(
            trade_experience,
            TradeExperience,
        ):
            raise TypeError(
                "remember_trade_outcome requires "
                "TradeExperience."
            )

        meaning = {
            "event": "trade_outcome",
            "trade_id": trade_experience.trade_id,
            "outcome": trade_experience.outcome,
            "reason": trade_experience.reason,
            "context": context or {},
        }

        experience = Experience(
            source="trading",
            content=json.dumps(
                meaning,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

        self.memory.save(experience)

        return experience