"""
TODOBA Execution Mission Release Guard

Determines whether an authenticated Trusted Agent is
currently eligible to receive an execution mission.

Release requires:

- Broker State exists for the authenticated Agent
- Broker State has a Cloud receive timestamp
- Broker State is fresh
- Broker State account matches the authoritative
  Trusted Agent account binding

This component does not:

- pop execution missions
- acquire delivery leases
- mutate execution lifecycle state
- execute broker orders
"""

from collections.abc import Callable
from datetime import UTC
from datetime import datetime

from backend.trading.execution.broker_state import (
    BrokerState,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)


def _utc_now() -> datetime:
    return datetime.now(
        UTC
    )


class ExecutionMissionReleaseGuard:
    """
    Fail-closed guard for execution mission release.
    """

    def __init__(
        self,
        *,
        broker_state_store: BrokerStateStore,
        account_binding_guard: TrustedAgentAccountBindingGuard,
        max_age_seconds: float,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not isinstance(
            broker_state_store,
            BrokerStateStore,
        ):
            raise TypeError(
                "ExecutionMissionReleaseGuard requires "
                "BrokerStateStore."
            )

        if not isinstance(
            account_binding_guard,
            TrustedAgentAccountBindingGuard,
        ):
            raise TypeError(
                "ExecutionMissionReleaseGuard requires "
                "TrustedAgentAccountBindingGuard."
            )

        if (
            not isinstance(
                max_age_seconds,
                (int, float),
            )
            or isinstance(
                max_age_seconds,
                bool,
            )
        ):
            raise TypeError(
                "max_age_seconds must be numeric."
            )

        if max_age_seconds <= 0:
            raise ValueError(
                "max_age_seconds must be greater than zero."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self.broker_state_store = (
            broker_state_store
        )

        self.account_binding_guard = (
            account_binding_guard
        )

        self.max_age_seconds = float(
            max_age_seconds
        )

        self.clock = clock

    def require_ready(
        self,
        *,
        agent_id: str,
    ) -> BrokerState:
        state = (
            self.broker_state_store.get_for_agent(
                agent_id=agent_id
            )
        )

        if state is None:
            raise RuntimeError(
                "Broker state is not available "
                "for Trusted Agent."
            )

        received_at = (
            self.broker_state_store
            .get_received_at_for_agent(
                agent_id=agent_id
            )
        )

        if received_at is None:
            raise RuntimeError(
                "Broker state receive time "
                "is not available."
            )

        if (
            received_at.tzinfo is None
            or received_at.utcoffset() is None
        ):
            raise RuntimeError(
                "Broker state receive time "
                "must be timezone-aware."
            )

        current_time = self.clock()

        if not isinstance(
            current_time,
            datetime,
        ):
            raise RuntimeError(
                "Release guard clock must "
                "return datetime."
            )

        if (
            current_time.tzinfo is None
            or current_time.utcoffset() is None
        ):
            raise RuntimeError(
                "Release guard clock must return "
                "timezone-aware datetime."
            )

        age_seconds = (
            current_time.astimezone(
                UTC
            )
            - received_at.astimezone(
                UTC
            )
        ).total_seconds()

        if age_seconds < 0:
            raise RuntimeError(
                "Broker state receive time "
                "is in the future."
            )

        if (
            age_seconds
            > self.max_age_seconds
        ):
            raise RuntimeError(
                "Broker state is stale."
            )

        try:
            self.account_binding_guard.require_binding(
                agent_id=agent_id,
                account_fingerprint=(
                    state.account_fingerprint
                ),
            )
        except RuntimeError as error:
            raise RuntimeError(
                "Broker state does not match "
                "authoritative account binding."
            ) from error

        return state