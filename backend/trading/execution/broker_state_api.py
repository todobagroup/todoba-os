"""
TODOBA Broker State API

Provides the authenticated HTTP boundary used by
Trusted Agents to publish current broker/account state.

This component does not:

- make trading decisions
- calculate lot size
- execute broker orders
- own broker-state persistence
"""

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from backend.trading.execution.broker_state import (
    BrokerState,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
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

    symbol: str

    bid: float
    ask: float
    spread_points: float


def create_broker_state_router(
    *,
    store: BrokerStateStore,
    authenticator: TrustedAgentAuthenticator,
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

    require_trusted_agent = (
        create_trusted_agent_authentication_dependency(
            authenticator
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
            symbol=request.symbol,
            bid=request.bid,
            ask=request.ask,
            spread_points=request.spread_points,
        )

        store.save(
            state
        )

        return {
            "status": "stored",
            "account_fingerprint": (
                state.account_fingerprint
            ),
            "symbol": state.symbol,
        }

    return router