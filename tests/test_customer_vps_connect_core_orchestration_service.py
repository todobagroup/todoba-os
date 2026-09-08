import pytest

from backend.commercial.customer_vps_connect_grant_http_client import (
    CustomerVPSConnectGrantHttpClient,
    CustomerVPSConnectGrantTransportResult,
)

from backend.commercial.customer_vps_connect_core_orchestration_service import (
    CustomerVPSConnectCoreOrchestrationResult,
    CustomerVPSConnectCoreOrchestrationService,
)


BASE_URL = "https://api.todobagroup.com"
ACTIVATION_CODE = "setup-activation-example"
FINGERPRINT = "broker|server|123456"
OTHER_FINGERPRINT = "broker|server|999999"
GRANT = "vps-connect-grant.example"
EXPIRES_AT = "2026-09-08T03:00:00+00:00"


def _client(monkeypatch, calls):
    client = CustomerVPSConnectGrantHttpClient(
        cloud_base_url=BASE_URL,
    )

    def issue(
        *,
        activation_code,
        account_fingerprint,
    ):
        calls.append(
            (
                activation_code,
                account_fingerprint,
            )
        )
        return CustomerVPSConnectGrantTransportResult(
            grant_credential=GRANT,
            expires_at=EXPIRES_AT,
        )

    monkeypatch.setattr(
        client,
        "issue",
        issue,
    )
    return client


def test_first_prepare_acquires_grant_and_returns_customer_safe_result(
    monkeypatch,
):
    calls = []

    service = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=_client(
            monkeypatch,
            calls,
        )
    )

    result = service.prepare(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=FINGERPRINT,
    )

    assert calls == [
        (
            ACTIVATION_CODE,
            FINGERPRINT,
        )
    ]

    assert result == CustomerVPSConnectCoreOrchestrationResult(
        status="grant_ready",
        expires_at=EXPIRES_AT,
    )

    assert not hasattr(
        result,
        "grant_credential",
    )

    assert GRANT not in repr(result)


def test_same_account_reuses_in_memory_grant_without_second_http_issue(
    monkeypatch,
):
    calls = []

    service = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=_client(
            monkeypatch,
            calls,
        )
    )

    first = service.prepare(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=FINGERPRINT,
    )

    second = service.prepare(
        activation_code="another-code-not-used",
        account_fingerprint=FINGERPRINT,
    )

    assert first == second
    assert len(calls) == 1


def test_account_identity_change_is_fail_closed(
    monkeypatch,
):
    calls = []

    service = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=_client(
            monkeypatch,
            calls,
        )
    )

    service.prepare(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=FINGERPRINT,
    )

    with pytest.raises(
        RuntimeError,
        match="account",
    ):
        service.prepare(
            activation_code=ACTIVATION_CODE,
            account_fingerprint=OTHER_FINGERPRINT,
        )

    assert len(calls) == 1


def test_activation_code_is_not_retained_after_prepare(
    monkeypatch,
):
    calls = []

    service = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=_client(
            monkeypatch,
            calls,
        )
    )

    service.prepare(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=FINGERPRINT,
    )

    assert ACTIVATION_CODE not in repr(service)
    assert ACTIVATION_CODE not in vars(service).values()


def test_grant_is_not_exposed_by_service_repr(
    monkeypatch,
):
    calls = []

    service = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=_client(
            monkeypatch,
            calls,
        )
    )

    service.prepare(
        activation_code=ACTIVATION_CODE,
        account_fingerprint=FINGERPRINT,
    )

    assert GRANT not in repr(service)


@pytest.mark.parametrize(
    "activation_code,account_fingerprint",
    [
        ("", FINGERPRINT),
        ("   ", FINGERPRINT),
        (ACTIVATION_CODE, ""),
        (ACTIVATION_CODE, "   "),
    ],
)
def test_required_inputs_fail_before_transport(
    monkeypatch,
    activation_code,
    account_fingerprint,
):
    calls = []

    service = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=_client(
            monkeypatch,
            calls,
        )
    )

    with pytest.raises(
        (TypeError, ValueError),
    ):
        service.prepare(
            activation_code=activation_code,
            account_fingerprint=account_fingerprint,
        )

    assert calls == []


def test_invalid_transport_result_fails_closed(
    monkeypatch,
):
    client = CustomerVPSConnectGrantHttpClient(
        cloud_base_url=BASE_URL,
    )

    monkeypatch.setattr(
        client,
        "issue",
        lambda **kwargs: object(),
    )

    service = CustomerVPSConnectCoreOrchestrationService(
        grant_http_client=client,
    )

    with pytest.raises(RuntimeError):
        service.prepare(
            activation_code=ACTIVATION_CODE,
            account_fingerprint=FINGERPRINT,
        )


def test_owner_has_no_persistence_or_setup_dependency():
    from pathlib import Path

    source = Path(
        "backend/commercial/"
        "customer_vps_connect_core_orchestration_service.py"
    ).read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "backend.main",
        "CustomerVPSConnectGrantStore",
        "customer_setup",
        "write_text",
        "write_bytes",
        "initialize_empty",
    ):
        assert forbidden not in source
