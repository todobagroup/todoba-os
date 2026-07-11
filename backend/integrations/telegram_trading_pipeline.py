"""
TODOBA Telegram Trading Pipeline

Transforms normalized Telegram IncomingSignal objects into
validated DRY-RUN execution plans.

Phase 1 safety rule:
This module must not send orders to MT5.
"""

from dataclasses import asdict
from typing import Any

from backend.trading.execution.execution_planner import create_plan
from backend.trading.parser.signal_parser import parse_signal
from backend.trading.profile.trading_profile import TradingProfile
from backend.trading.signal.incoming_signal import IncomingSignal
from backend.trading.validation.validation_policy import validate


class TelegramTradingPipeline:
    """
    Process Telegram signals safely.

    Responsibilities:

    1. Detect duplicate Telegram messages.
    2. Parse the human message.
    3. Validate the trading Signal.
    4. Create an ExecutionPlan.
    5. Return a structured DRY-RUN result.

    Non-responsibility:

    - This pipeline does not send live MT5 orders.
    """

    def __init__(
        self,
        profile: TradingProfile,
    ):
        if profile is None:
            raise ValueError(
                "Trading profile is required."
            )

        self.profile = profile

        self._processed_message_keys: set[
            tuple[int, int]
        ] = set()

    def process(
        self,
        incoming_signal: IncomingSignal,
    ) -> dict[str, Any]:
        """
        Process one IncomingSignal and return a structured result.

        Invalid messages fail safely and do not stop the listener.
        """

        if not isinstance(
            incoming_signal,
            IncomingSignal,
        ):
            raise TypeError(
                "TelegramTradingPipeline requires IncomingSignal."
            )

        source_key = incoming_signal.source_key()

        if (
            source_key is not None
            and source_key in self._processed_message_keys
        ):
            return {
                "status": "duplicate",
                "mode": "DRY_RUN",
                "source": incoming_signal.source,
                "chat_id": incoming_signal.chat_id,
                "message_id": incoming_signal.message_id,
                "error": "Telegram message already processed.",
                "live_order_sent": False,
            }

        try:
            signal = parse_signal(
                incoming_signal.message
            )

            validation_result = validate(
                signal,
                self.profile,
            )

            if not validation_result.passed:
                return {
                    "status": "rejected",
                    "mode": "DRY_RUN",
                    "source": incoming_signal.source,
                    "sender": incoming_signal.sender,
                    "sender_id": incoming_signal.sender_id,
                    "chat_id": incoming_signal.chat_id,
                    "message_id": incoming_signal.message_id,
                    "original_message": incoming_signal.message,
                    "signal": asdict(signal),
                    "validation": {
                        "passed": validation_result.passed,
                        "errors": validation_result.errors,
                    },
                    "errors": validation_result.errors,
                    "live_order_sent": False,
                }

            execution_plan = create_plan(
                signal,
                self.profile,
            )

            if source_key is not None:
                self._processed_message_keys.add(
                    source_key
                )

            return {
                "status": "planned",
                "mode": "DRY_RUN",
                "source": incoming_signal.source,
                "sender": incoming_signal.sender,
                "sender_id": incoming_signal.sender_id,
                "chat_id": incoming_signal.chat_id,
                "message_id": incoming_signal.message_id,
                "received_at": (
                    incoming_signal.received_at.isoformat()
                ),
                "original_message": incoming_signal.message,
                "signal": asdict(signal),
                "validation": {
                    "passed": validation_result.passed,
                    "errors": validation_result.errors,
                },
                "execution_plan": asdict(
                    execution_plan
                ),
                "live_order_sent": False,
            }

        except (TypeError, ValueError) as error:
            return {
                "status": "rejected",
                "mode": "DRY_RUN",
                "source": incoming_signal.source,
                "sender": incoming_signal.sender,
                "sender_id": incoming_signal.sender_id,
                "chat_id": incoming_signal.chat_id,
                "message_id": incoming_signal.message_id,
                "original_message": incoming_signal.message,
                "errors": [str(error)],
                "live_order_sent": False,
            }

    def processed_count(self) -> int:
        """
        Return the number of Telegram messages protected
        by the current in-memory duplicate registry.
        """

        return len(
            self._processed_message_keys
        )