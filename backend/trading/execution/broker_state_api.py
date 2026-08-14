"""
TODOBA Broker State API

Provides authenticated HTTP boundaries used by:

- Trusted Agents to publish current broker state
- trusted Executors to read the latest Agent state

This component does not:

- make trading decisions
- calculate lot size
- execute broker orders
- own broker-state persistence
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel

from backend.trading.execution.broker_state import (
    BrokerState,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)
from backend.trading.execution.executor_authentication_dependency import (
    create_executor_authentication_dependency,
)
from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)
from backend.trading.execution.trusted_agent_authentication_dependency import (
    create_trusted_agent_authentication_dependency,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)


class BrokerStateRequest(BaseModel):
    account_fingerprint: str

    equity: float
    open_position_count: int
    pending_order_count: int

    symbol: str

    bid: float
    ask: float
    spread_points: float


def create_broker_state_router(
    *,
    store: BrokerStateStore,
    authenticator: TrustedAgentAuthenticator,
    executor_authenticator: ExecutorAuthenticator,
) -> APIRouter:
    if not isinstance(
        store,
        BrokerStateStore,
    ):
        raise TypeError(
            "create_broker_state_router requires "
            "BrokerStateStore."
        )

    if not isinstance(
        authenticator,
        TrustedAgentAuthenticator,
    ):
        raise TypeError(
            "create_broker_state_router requires "
            "TrustedAgentAuthenticator."
        )

    if not isinstance(
        executor_authenticator,
        ExecutorAuthenticator,
    ):
        raise TypeError(
            "create_broker_state_router requires "
            "ExecutorAuthenticator."
        )

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
        )
    )

    require_executor = (
        create_executor_authentication_dependency(
            executor_authenticator
        )
    )

    router = APIRouter()

    @router.post(
        "/broker/state"
    )
    def publish_broker_state(
        request: BrokerStateRequest,
        agent_id: str = Depends(
            require_trusted_agent
        ),
    ):
        state = BrokerState(
            account_fingerprint=(
                request.account_fingerprint
            ),
            equity=request.equity,
            open_position_count=(
                request.open_position_count
            ),
            pending_order_count=(
                request.pending_order_count
            ),
            symbol=request.symbol,
            bid=request.bid,
            ask=request.ask,
            spread_points=request.spread_points,
        )

        store.save(
            state,
            agent_id=agent_id,
        )

        return {
            "status": "stored",
            "account_fingerprint": (
                state.account_fingerprint
            ),
            "symbol": state.symbol,
        }

    @router.get(
        "/broker/state/latest"
    )
    def read_latest_broker_state(
        agent_id: str,
        executor_id: str = Depends(
            require_executor
        ),
    ):
        state = store.get_for_agent(
            agent_id=agent_id,
        )

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Broker state not found.",
            )

        return {
            "status": "available",
            "agent_id": agent_id,
            "account_fingerprint": (
                state.account_fingerprint
            ),
            "equity": state.equity,
            "open_position_count": (
                state.open_position_count
            ),
            "pending_order_count": (
                state.pending_order_count
            ),
            "symbol": state.symbol,
            "bid": state.bid,
            "ask": state.ask,
            "spread_points": (
                state.spread_points
            ),
        }

    return router