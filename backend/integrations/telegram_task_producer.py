"""
TODOBA Telegram Task Producer

Transforms a normalized Telegram IncomingSignal into
an approved TODOBA organizational trading Task.

Architecture:

IncomingSignal
    ↓
Signal Parser
    ↓
Trading Profile Validation
    ↓
TradingIntent
    ↓
DecisionGateway
    ↓
IntentTaskAdapter
    ↓
Task

This component does not dispatch or execute the Task.
"""

from dataclasses import dataclass
from typing import Any, Optional

from backend.task.task import Task
from backend.trading.decision.decision_gateway import (
    DecisionGateway,
)
from backend.trading.intent.signal_intent_adapter import (
    SignalIntentAdapter,
)
from backend.trading.intent.trading_intent import (
    TradingIntent,
)
from backend.trading.models.signal import Signal
from backend.trading.parser.signal_parser import (
    parse_signal,
)
from backend.trading.profile.trading_profile import (
    TradingProfile,
)
from backend.trading.signal.incoming_signal import (
    IncomingSignal,
)
from backend.trading.validation.validation_policy import (
    validate,
)


@dataclass(frozen=True)
class TelegramTaskProductionResult:
    """
    Structured outcome of Telegram Task production.
    """

    status: str
    incoming_signal: IncomingSignal
    signal: Optional[Signal] = None
    intent: Optional[TradingIntent] = None
    task: Optional[Task] = None
    decision: Optional[Any] = None
    errors: tuple[str, ...] = ()


class TelegramTaskProducer:
    """
    Produce organizational trading Tasks from Telegram input.

    DecisionGateway remains the only component allowed to
    approve an intent and convert it into a Task.
    """

    def __init__(
        self,
        profile: TradingProfile,
        decision_gateway: Optional[
            DecisionGateway
        ] = None,
    ):
        if not isinstance(
            profile,
            TradingProfile,
        ):
            raise TypeError(
                "TelegramTaskProducer requires "
                "TradingProfile."
            )

        self.profile = profile

        self.decision_gateway = (
            decision_gateway
            if decision_gateway is not None
            else DecisionGateway()
        )

        self.signal_intent_adapter = (
            SignalIntentAdapter()
        )

    def produce(
        self,
        incoming_signal: IncomingSignal,
        *,
        open_position_count: int,
        spread_ok: bool,
        market_open: bool,
        risk_ok: bool,
    ) -> TelegramTaskProductionResult:
        """
        Produce one approved organizational trading Task.

        Existing trades are allowed while their count remains
        below the profile's maximum open-trade limit.
        """

        if not isinstance(
            incoming_signal,
            IncomingSignal,
        ):
            raise TypeError(
                "TelegramTaskProducer requires "
                "IncomingSignal."
            )

        if not isinstance(
            open_position_count,
            int,
        ):
            raise TypeError(
                "open_position_count must be int."
            )

        if open_position_count < 0:
            raise ValueError(
                "open_position_count cannot be negative."
            )

        try:
            signal = parse_signal(
                incoming_signal.message
            )

            validation_result = validate(
                signal,
                self.profile,
            )

            if not validation_result.passed:
                return TelegramTaskProductionResult(
                    status="profile_rejected",
                    incoming_signal=incoming_signal,
                    signal=signal,
                    errors=tuple(
                        validation_result.errors
                    ),
                )

            intent = (
                self.signal_intent_adapter.to_intent(
                    signal
                )
            )

            task, decision = (
                self.decision_gateway
                .create_task_if_approved(
                    intent=intent,
                    open_position_count=(
                        open_position_count
                    ),
                    max_open_trades=(
                        self.profile.max_open_trades
                    ),
                    spread_ok=spread_ok,
                    market_open=market_open,
                    risk_ok=risk_ok,
                )
            )

            if task is None:
                return TelegramTaskProductionResult(
                    status="decision_rejected",
                    incoming_signal=incoming_signal,
                    signal=signal,
                    intent=intent,
                    decision=decision,
                    errors=(
                        "Trading intent was rejected "
                        "by DecisionGateway.",
                    ),
                )

            return TelegramTaskProductionResult(
                status="task_created",
                incoming_signal=incoming_signal,
                signal=signal,
                intent=intent,
                task=task,
                decision=decision,
            )

        except (TypeError, ValueError) as error:
            return TelegramTaskProductionResult(
                status="invalid_signal",
                incoming_signal=incoming_signal,
                errors=(str(error),),
            )