import inspect
from pathlib import Path

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


ACTIVATION_CODE = "setup-activation-finish-proof"
ACCOUNT_FINGERPRINT = "Broker-Pro:12345678"
GRANT = "vps-connect-grant.finish.secret"
EXPIRES_AT = "2026-09-08T15:00:00+00:00"


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


def _core(
    *,
    statuses,
    prepare=True,
):
    grant_client = FakeGrantHttpClient()

    live_proof_client = FakeLiveProofHttpClient(
        statuses=statuses,
    )

    core = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=grant_client,
        live_proof_http_client=live_proof_client,
    )

    if prepare:
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


def test_finish_is_blocked_before_prepare():
    (
        core,
        _,
        live_proof_client,
    ) = _core(
        statuses=[],
        prepare=False,
    )

    result = core.finish_readiness()

    assert result.status == "finish_blocked"
    assert live_proof_client.calls == []


def test_finish_is_blocked_after_grant_before_live_proof():
    (
        core,
        _,
        live_proof_client,
    ) = _core(
        statuses=[],
    )

    result = core.finish_readiness()

    assert result.status == "finish_blocked"
    assert live_proof_client.calls == []


def test_vps_pending_keeps_finish_blocked():
    (
        core,
        _,
        live_proof_client,
    ) = _core(
        statuses=[
            "vps_pending",
        ],
    )

    proof = core.check_live_proof()

    assert proof.status == "vps_pending"

    readiness = core.finish_readiness()

    assert readiness.status == "finish_blocked"

    assert live_proof_client.calls == [
        GRANT,
    ]


def test_vps_online_makes_finish_ready():
    (
        core,
        _,
        live_proof_client,
    ) = _core(
        statuses=[
            "vps_online",
        ],
    )

    proof = core.check_live_proof()

    assert proof.status == "vps_online"

    readiness = core.finish_readiness()

    assert readiness.status == "finish_ready"

    assert live_proof_client.calls == [
        GRANT,
    ]


def test_finish_reblocks_if_latest_proof_returns_pending():
    (
        core,
        _,
        live_proof_client,
    ) = _core(
        statuses=[
            "vps_online",
            "vps_pending",
        ],
    )

    first = core.check_live_proof()

    assert first.status == "vps_online"
    assert (
        core.finish_readiness().status
        == "finish_ready"
    )

    second = core.check_live_proof()

    assert second.status == "vps_pending"
    assert (
        core.finish_readiness().status
        == "finish_blocked"
    )

    assert live_proof_client.calls == [
        GRANT,
        GRANT,
    ]


def test_finish_readiness_does_not_poll_network():
    (
        core,
        _,
        live_proof_client,
    ) = _core(
        statuses=[
            "vps_online",
        ],
    )

    core.check_live_proof()

    calls_before = list(
        live_proof_client.calls
    )

    first = core.finish_readiness()
    second = core.finish_readiness()

    assert first.status == "finish_ready"
    assert second.status == "finish_ready"

    assert (
        live_proof_client.calls
        == calls_before
    )


def test_finish_readiness_has_no_authority_input():
    signature = inspect.signature(
        CustomerVPSConnectCoreOrchestrationService
        .finish_readiness
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
    )


def test_finish_result_surface_is_customer_safe():
    (
        core,
        _,
        _,
    ) = _core(
        statuses=[
            "vps_online",
        ],
    )

    core.check_live_proof()

    result = core.finish_readiness()

    assert tuple(
        result.__dataclass_fields__
    ) == (
        "status",
    )

    assert GRANT not in repr(result)


def test_core_finish_gate_has_no_gui_polling_or_persistence_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_core_orchestration_service.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "customer_setup_gui_shell",
        "tkinter",
        "ttk.",
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