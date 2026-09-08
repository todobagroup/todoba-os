import inspect

import pytest

from backend.commercial.customer_vps_connect_core_orchestration_service import (
    CustomerVPSConnectCoreOrchestrationService,
)

from backend.commercial.customer_vps_connect_grant_http_client import (
    CustomerVPSConnectGrantHttpClient,
    CustomerVPSConnectGrantTransportResult,
)

from backend.commercial.customer_vps_connect_live_proof_http_client import (
    CustomerVPSConnectLiveProofHttpClient,
    CustomerVPSConnectLiveProofTransportResult,
)


ACTIVATION_CODE = "setup-activation-proof"
ACCOUNT_FINGERPRINT = "Broker-Pro:12345678"
GRANT = "vps-connect-grant.secret.proof"
EXPIRES_AT = "2026-09-08T12:00:00+00:00"


class FakeGrantHttpClient(
    CustomerVPSConnectGrantHttpClient
):
    def __init__(self):
        self.calls = []

    def issue(
        self,
        *,
        activation_code,
        account_fingerprint,
    ):
        self.calls.append(
            (
                activation_code,
                account_fingerprint,
            )
        )

        return CustomerVPSConnectGrantTransportResult(
            grant_credential=GRANT,
            expires_at=EXPIRES_AT,
        )


class FakeLiveProofHttpClient(
    CustomerVPSConnectLiveProofHttpClient
):
    def __init__(
        self,
        statuses,
    ):
        self.statuses = list(statuses)
        self.calls = []

    def verify(
        self,
        *,
        grant_credential,
    ):
        self.calls.append(
            grant_credential
        )

        return CustomerVPSConnectLiveProofTransportResult(
            status=self.statuses.pop(0),
        )


def _prepared_core(
    *,
    statuses,
):
    grant_client = FakeGrantHttpClient()

    live_proof_client = (
        FakeLiveProofHttpClient(
            statuses=statuses,
        )
    )

    core = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=grant_client,
        live_proof_http_client=live_proof_client,
    )

    prepared = core.prepare(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=ACCOUNT_FINGERPRINT,
    )

    assert prepared.status == "grant_ready"

    return (
        core,
        grant_client,
        live_proof_client,
    )


def test_check_live_proof_uses_private_in_memory_grant():
    (
        core,
        grant_client,
        live_proof_client,
    ) = _prepared_core(
        statuses=[
            "vps_pending",
        ],
    )

    result = core.check_live_proof()

    assert result.status == "vps_pending"

    assert grant_client.calls == [
        (
            ACTIVATION_CODE,
            ACCOUNT_FINGERPRINT,
        )
    ]

    assert live_proof_client.calls == [
        GRANT
    ]

    assert tuple(
        result.__dataclass_fields__
    ) == (
        "status",
    )

    assert GRANT not in repr(result)


def test_live_proof_converges_pending_then_online():
    (
        core,
        _,
        live_proof_client,
    ) = _prepared_core(
        statuses=[
            "vps_pending",
            "vps_online",
        ],
    )

    first = core.check_live_proof()
    second = core.check_live_proof()

    assert first.status == "vps_pending"
    assert second.status == "vps_online"

    assert live_proof_client.calls == [
        GRANT,
        GRANT,
    ]


def test_check_live_proof_before_prepare_fails_closed():
    live_proof_client = FakeLiveProofHttpClient(
        statuses=[
            "vps_online",
        ],
    )

    core = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=FakeGrantHttpClient(),
        live_proof_http_client=live_proof_client,
    )

    with pytest.raises(
        RuntimeError,
    ):
        core.check_live_proof()

    assert live_proof_client.calls == []


def test_check_live_proof_has_no_authority_input():
    signature = inspect.signature(
        CustomerVPSConnectCoreOrchestrationService
        .check_live_proof
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
    )


def test_live_proof_client_may_be_absent_for_existing_prepare_flow():
    core = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=FakeGrantHttpClient(),
    )

    result = core.prepare(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=ACCOUNT_FINGERPRINT,
    )

    assert result.status == "grant_ready"

    with pytest.raises(
        RuntimeError,
    ):
        core.check_live_proof()


def test_invalid_live_proof_transport_result_fails_closed():
    class InvalidLiveProofClient(
        CustomerVPSConnectLiveProofHttpClient
    ):
        def __init__(self):
            pass

        def verify(
            self,
            *,
            grant_credential,
        ):
            return object()

    core = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=FakeGrantHttpClient(),
        live_proof_http_client=InvalidLiveProofClient(),
    )

    core.prepare(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=ACCOUNT_FINGERPRINT,
    )

    with pytest.raises(
        RuntimeError,
    ):
        core.check_live_proof()


def test_core_repr_never_exposes_grant():
    (
        core,
        _,
        _,
    ) = _prepared_core(
        statuses=[
            "vps_pending",
        ],
    )

    assert GRANT not in repr(core)

    core.check_live_proof()

    assert GRANT not in repr(core)


def test_core_owner_does_not_acquire_polling_or_persistence_authority():
    from pathlib import Path

    source = Path(
        "backend/commercial/"
        "customer_vps_connect_core_orchestration_service.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "time.sleep",
        "asyncio.sleep",
        "threading",
        "while True",
        "write_text",
        "write_bytes",
        "initialize_empty",
        "BrokerStateStore",
        "MetaTrader5",
        "common.ini",
        "WebRequestUrl",
        "subprocess",
        "pywinauto",
        "uiautomation",
    ):
        assert forbidden not in source