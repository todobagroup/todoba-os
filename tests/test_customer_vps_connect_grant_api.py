from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_vps_connect_grant_api import (
    create_customer_vps_connect_grant_router,
)
from backend.commercial.customer_vps_connect_grant_service import (
    CustomerVPSConnectGrantIssuance,
)


_PATH = "/customer/vps-connect/grant"

_ACTIVATION_CODE = "activation-code-001"
_ACCOUNT_FINGERPRINT = "Broker-Server:12345678"

_NOW = datetime(
    2026,
    9,
    7,
    15,
    0,
    tzinfo=timezone.utc,
)


def _build_client(
    issue_vps_connect_grant,
) -> TestClient:
    app = FastAPI()

    app.include_router(
        create_customer_vps_connect_grant_router(
            issue_vps_connect_grant=(
                issue_vps_connect_grant
            ),
        )
    )

    return TestClient(app)


def _issuance():
    return CustomerVPSConnectGrantIssuance(
        grant_id="grant-001",
        grant_credential="opaque-vps-connect-grant",
        customer_id="customer-001",
        deployment_id="deployment-001",
        agent_id="trusted-agent-001",
        account_fingerprint=_ACCOUNT_FINGERPRINT,
        issued_at=_NOW,
        expires_at=(
            _NOW
            + timedelta(minutes=10)
        ),
    )


def test_success_returns_only_customer_safe_grant(
) -> None:
    calls = []

    def issue_vps_connect_grant(
        **kwargs,
    ):
        calls.append(kwargs)
        return _issuance()

    client = _build_client(
        issue_vps_connect_grant
    )

    response = client.post(
        _PATH,
        json={
            "activation_code": _ACTIVATION_CODE,
            "account_fingerprint": (
                _ACCOUNT_FINGERPRINT
            ),
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )

    assert response.json() == {
        "grant_credential": (
            "opaque-vps-connect-grant"
        ),
        "expires_at": (
            _NOW
            + timedelta(minutes=10)
        ).isoformat(),
    }

    assert calls == [
        {
            "activation_code": _ACTIVATION_CODE,
            "account_fingerprint": (
                _ACCOUNT_FINGERPRINT
            ),
        }
    ]

    body = response.json()

    for forbidden in (
        "customer_id",
        "deployment_id",
        "agent_id",
        "setup_activation_id",
        "grant_id",
    ):
        assert forbidden not in body


def test_business_rejection_returns_generic_403(
) -> None:
    def issue_vps_connect_grant(
        **kwargs,
    ):
        raise ValueError(
            "sensitive deployment mismatch"
        )

    client = _build_client(
        issue_vps_connect_grant
    )

    response = client.post(
        _PATH,
        json={
            "activation_code": _ACTIVATION_CODE,
            "account_fingerprint": (
                _ACCOUNT_FINGERPRINT
            ),
        },
    )

    assert response.status_code == 403
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )

    assert (
        "sensitive deployment mismatch"
        not in response.text
    )


def test_internal_failure_returns_generic_500(
) -> None:
    def issue_vps_connect_grant(
        **kwargs,
    ):
        raise RuntimeError(
            "sensitive internal failure"
        )

    client = _build_client(
        issue_vps_connect_grant
    )

    response = client.post(
        _PATH,
        json={
            "activation_code": _ACTIVATION_CODE,
            "account_fingerprint": (
                _ACCOUNT_FINGERPRINT
            ),
        },
    )

    assert response.status_code == 500
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )

    assert (
        "sensitive internal failure"
        not in response.text
    )


def test_invalid_business_result_fails_closed(
) -> None:
    def issue_vps_connect_grant(
        **kwargs,
    ):
        return object()

    client = _build_client(
        issue_vps_connect_grant
    )

    response = client.post(
        _PATH,
        json={
            "activation_code": _ACTIVATION_CODE,
            "account_fingerprint": (
                _ACCOUNT_FINGERPRINT
            ),
        },
    )

    assert response.status_code == 500
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )


def test_extra_customer_authority_is_forbidden(
) -> None:
    calls = []

    def issue_vps_connect_grant(
        **kwargs,
    ):
        calls.append(kwargs)
        return _issuance()

    client = _build_client(
        issue_vps_connect_grant
    )

    response = client.post(
        _PATH,
        json={
            "activation_code": _ACTIVATION_CODE,
            "account_fingerprint": (
                _ACCOUNT_FINGERPRINT
            ),
            "deployment_id": "deployment-attacker",
        },
    )

    assert response.status_code == 422
    assert calls == []
