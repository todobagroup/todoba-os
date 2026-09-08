from datetime import UTC
from datetime import datetime
from datetime import timedelta
from inspect import signature
from pathlib import Path

import pytest

from backend.commercial.customer_vps_connect_grant_service import (
    CustomerVPSConnectGrantAuthorization,
    CustomerVPSConnectGrantService,
)

from backend.commercial.customer_vps_connect_live_proof_service import (
    CustomerVPSConnectLiveProofResult,
    CustomerVPSConnectLiveProofService,
)

from backend.trading.execution.broker_state import (
    BrokerState,
)

from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)


AGENT_ID = "trusted-agent-live-proof-001"
ACCOUNT_FINGERPRINT = "RoboForex-Pro:68351319"
GRANT = "vps-connect-grant.proof.secret"

NOW = datetime(
    2026,
    9,
    8,
    3,
    0,
    0,
    tzinfo=UTC,
)


class FakeGrantService(
    CustomerVPSConnectGrantService,
):
    def __init__(
        self,
        *,
        authorization=None,
        error=None,
    ):
        self.authorization = (
            authorization
        )
        self.error = error
        self.calls = []

    def authorize(
        self,
        *,
        grant_credential,
    ):
        self.calls.append(
            grant_credential
        )

        if self.error is not None:
            raise self.error

        return self.authorization


def _authorization():
    return CustomerVPSConnectGrantAuthorization(
        customer_id="customer-proof-001",
        deployment_id="deployment-proof-001",
        agent_id=AGENT_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
        expires_at=(
            NOW
            + timedelta(minutes=5)
        ),
    )


def _state(
    *,
    account_fingerprint=ACCOUNT_FINGERPRINT,
):
    return BrokerState(
        account_fingerprint=(
            account_fingerprint
        ),
        equity=10000.0,
        open_position_count=0,
        pending_order_count=0,
        symbol="EURUSD",
        bid=1.1000,
        ask=1.1002,
        spread_points=2.0,
    )


def _store(
    *,
    received_at,
    state=None,
):
    store = BrokerStateStore(
        clock=lambda: received_at,
    )

    if state is not None:
        store.save(
            state,
            agent_id=AGENT_ID,
        )

    return store


def _service(
    *,
    store,
    grant_service=None,
):
    return CustomerVPSConnectLiveProofService(
        grant_service=(
            grant_service
            or FakeGrantService(
                authorization=_authorization(),
            )
        ),
        broker_state_store=store,
        clock=lambda: NOW,
    )


def test_fresh_matching_agent_state_is_vps_online():
    service = _service(
        store=_store(
            received_at=(
                NOW
                - timedelta(seconds=5)
            ),
            state=_state(),
        ),
    )

    result = service.verify(
        grant_credential=GRANT,
    )

    assert result == (
        CustomerVPSConnectLiveProofResult(
            status="vps_online",
        )
    )


def test_missing_broker_state_is_vps_pending():
    service = _service(
        store=_store(
            received_at=NOW,
        ),
    )

    assert service.verify(
        grant_credential=GRANT,
    ) == CustomerVPSConnectLiveProofResult(
        status="vps_pending",
    )


def test_wrong_bound_account_is_vps_pending():
    service = _service(
        store=_store(
            received_at=NOW,
            state=_state(
                account_fingerprint=(
                    "OtherBroker:999"
                ),
            ),
        ),
    )

    assert service.verify(
        grant_credential=GRANT,
    ) == CustomerVPSConnectLiveProofResult(
        status="vps_pending",
    )


def test_state_older_than_15_seconds_is_pending():
    service = _service(
        store=_store(
            received_at=(
                NOW
                - timedelta(seconds=16)
            ),
            state=_state(),
        ),
    )

    assert service.verify(
        grant_credential=GRANT,
    ) == CustomerVPSConnectLiveProofResult(
        status="vps_pending",
    )


def test_state_exactly_15_seconds_old_is_online():
    service = _service(
        store=_store(
            received_at=(
                NOW
                - timedelta(seconds=15)
            ),
            state=_state(),
        ),
    )

    assert service.verify(
        grant_credential=GRANT,
    ) == CustomerVPSConnectLiveProofResult(
        status="vps_online",
    )


def test_invalid_or_expired_grant_fails_closed():
    grant_service = FakeGrantService(
        error=ValueError(
            "Customer VPS Connect grant is invalid."
        ),
    )

    service = _service(
        store=_store(
            received_at=NOW,
        ),
        grant_service=grant_service,
    )

    with pytest.raises(
        ValueError,
        match="grant is invalid",
    ):
        service.verify(
            grant_credential=GRANT,
        )


def test_verify_accepts_only_grant_credential():
    params = list(
        signature(
            CustomerVPSConnectLiveProofService.verify
        ).parameters
    )

    assert params == [
        "self",
        "grant_credential",
    ]


def test_result_surface_contains_only_status():
    result = CustomerVPSConnectLiveProofResult(
        status="vps_online",
    )

    assert tuple(
        result.__dataclass_fields__
    ) == ("status",)

    assert not hasattr(
        result,
        "customer_id",
    )

    assert not hasattr(
        result,
        "deployment_id",
    )

    assert not hasattr(
        result,
        "agent_id",
    )

    assert not hasattr(
        result,
        "account_fingerprint",
    )


def test_owner_has_no_extra_runtime_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_live_proof_service.py"
    ).read_text(
        encoding="utf-8-sig",
    )

    for forbidden in (
        "MetaTrader5.initialize",
        "TERMINAL_VPS",
        "common.ini",
        "WebRequestUrl",
        "subprocess",
        "pywinauto",
        "uiautomation",
        "grant_store",
        ".save(",
        "write_text",
        "write_bytes",
        "initialize_empty",
    ):
        assert forbidden not in source