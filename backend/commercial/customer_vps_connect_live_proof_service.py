"""
TODOBA Customer VPS Connect Live Proof Service.

Consumes a short-lived VPS Connect grant and verifies
fresh runtime evidence from the already-bound Trusted Agent.

This owner reads existing runtime evidence only.
It does not create broker state or operate MetaTrader.
"""

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Callable
from typing import Literal

from backend.commercial.customer_vps_connect_grant_service import (
    CustomerVPSConnectGrantAuthorization,
    CustomerVPSConnectGrantService,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)


_LIVE_PROOF_MAX_AGE = timedelta(
    seconds=15,
)


def _utc_now() -> datetime:
    return datetime.now(
        UTC
    )


def _normalize_aware_datetime(
    value: datetime,
    *,
    name: str,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            f"{name} must be datetime."
        )

    if value.tzinfo is None:
        raise ValueError(
            f"{name} must be timezone-aware."
        )

    return value.astimezone(
        UTC
    )


@dataclass(
    frozen=True,
)
class CustomerVPSConnectLiveProofResult:
    status: Literal[
        "vps_pending",
        "vps_online",
    ]

    def __post_init__(
        self,
    ) -> None:
        if self.status not in (
            "vps_pending",
            "vps_online",
        ):
            raise ValueError(
                "status must be vps_pending "
                "or vps_online."
            )


class CustomerVPSConnectLiveProofService:
    def __init__(
        self,
        *,
        grant_service: CustomerVPSConnectGrantService,
        broker_state_store: BrokerStateStore,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not isinstance(
            grant_service,
            CustomerVPSConnectGrantService,
        ):
            raise TypeError(
                "grant_service must be "
                "CustomerVPSConnectGrantService."
            )

        if not isinstance(
            broker_state_store,
            BrokerStateStore,
        ):
            raise TypeError(
                "broker_state_store must be "
                "BrokerStateStore."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self._grant_service = (
            grant_service
        )
        self._broker_state_store = (
            broker_state_store
        )
        self._clock = clock

    def verify(
        self,
        *,
        grant_credential: str,
    ) -> CustomerVPSConnectLiveProofResult:
        authorization = (
            self._grant_service.authorize(
                grant_credential=(
                    grant_credential
                ),
            )
        )

        if not isinstance(
            authorization,
            CustomerVPSConnectGrantAuthorization,
        ):
            raise TypeError(
                "grant authorization must be "
                "CustomerVPSConnectGrantAuthorization."
            )

        broker_state = (
            self._broker_state_store.get_for_agent(
                agent_id=(
                    authorization.agent_id
                ),
            )
        )

        if broker_state is None:
            return self._pending()

        if (
            broker_state.account_fingerprint
            != authorization.account_fingerprint
        ):
            return self._pending()

        received_at = (
            self._broker_state_store
            .get_received_at_for_agent(
                agent_id=(
                    authorization.agent_id
                ),
            )
        )

        if received_at is None:
            return self._pending()

        normalized_received_at = (
            _normalize_aware_datetime(
                received_at,
                name="received_at",
            )
        )

        now = _normalize_aware_datetime(
            self._clock(),
            name="clock",
        )

        age = (
            now
            - normalized_received_at
        )

        if age < timedelta(0):
            return self._pending()

        if age > _LIVE_PROOF_MAX_AGE:
            return self._pending()

        return CustomerVPSConnectLiveProofResult(
            status="vps_online",
        )

    @staticmethod
    def _pending(
    ) -> CustomerVPSConnectLiveProofResult:
        return CustomerVPSConnectLiveProofResult(
            status="vps_pending",
        )