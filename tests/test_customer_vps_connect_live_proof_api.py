from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_vps_connect_live_proof_api import (
    CustomerVPSConnectLiveProofRequest,
    create_customer_vps_connect_live_proof_router,
)

from backend.commercial.customer_vps_connect_live_proof_service import (
    CustomerVPSConnectLiveProofResult,
)


_PATH = "/customer/vps-connect/live-proof"
_GRANT = "vps-connect-grant.proof.secret"


def _client(
    verify_vps_connect_live_proof,
):
    app = FastAPI()

    app.include_router(
        create_customer_vps_connect_live_proof_router(
            verify_vps_connect_live_proof=(
                verify_vps_connect_live_proof
            ),
        )
    )

    return TestClient(app)


def test_online_live_proof_returns_customer_safe_status():
    calls = []

    def verify_vps_connect_live_proof(
        **kwargs,
    ):
        calls.append(kwargs)

        return CustomerVPSConnectLiveProofResult(
            status="vps_online",
        )

    response = _client(
        verify_vps_connect_live_proof
    ).post(
        _PATH,
        json={
            "grant_credential": _GRANT,
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )
    assert response.json() == {
        "status": "vps_online",
    }

    assert calls == [
        {
            "grant_credential": _GRANT,
        }
    ]


def test_pending_live_proof_returns_customer_safe_status():
    def verify_vps_connect_live_proof(
        **kwargs,
    ):
        return CustomerVPSConnectLiveProofResult(
            status="vps_pending",
        )

    response = _client(
        verify_vps_connect_live_proof
    ).post(
        _PATH,
        json={
            "grant_credential": _GRANT,
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )
    assert response.json() == {
        "status": "vps_pending",
    }


def test_grant_credential_is_redacted_from_request_repr():
    request = CustomerVPSConnectLiveProofRequest(
        grant_credential=_GRANT,
    )

    assert _GRANT not in repr(request)


def test_invalid_grant_returns_generic_403():
    def verify_vps_connect_live_proof(
        **kwargs,
    ):
        raise ValueError(
            "sensitive grant authorization detail"
        )

    response = _client(
        verify_vps_connect_live_proof
    ).post(
        _PATH,
        json={
            "grant_credential": _GRANT,
        },
    )

    assert response.status_code == 403
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )
    assert (
        "sensitive grant authorization detail"
        not in response.text
    )
    assert _GRANT not in response.text


def test_internal_failure_returns_generic_500():
    def verify_vps_connect_live_proof(
        **kwargs,
    ):
        raise RuntimeError(
            "sensitive broker state failure"
        )

    response = _client(
        verify_vps_connect_live_proof
    ).post(
        _PATH,
        json={
            "grant_credential": _GRANT,
        },
    )

    assert response.status_code == 500
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )
    assert (
        "sensitive broker state failure"
        not in response.text
    )
    assert _GRANT not in response.text


def test_invalid_service_result_returns_generic_500():
    def verify_vps_connect_live_proof(
        **kwargs,
    ):
        return {
            "status": "vps_online",
        }

    response = _client(
        verify_vps_connect_live_proof
    ).post(
        _PATH,
        json={
            "grant_credential": _GRANT,
        },
    )

    assert response.status_code == 500
    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )


def test_extra_customer_authority_is_forbidden():
    calls = []

    def verify_vps_connect_live_proof(
        **kwargs,
    ):
        calls.append(kwargs)

        return CustomerVPSConnectLiveProofResult(
            status="vps_online",
        )

    response = _client(
        verify_vps_connect_live_proof
    ).post(
        _PATH,
        json={
            "grant_credential": _GRANT,
            "agent_id": "customer-supplied-agent",
        },
    )

    assert response.status_code == 422
    assert calls == []


def test_missing_grant_credential_is_rejected():
    calls = []

    def verify_vps_connect_live_proof(
        **kwargs,
    ):
        calls.append(kwargs)

        return CustomerVPSConnectLiveProofResult(
            status="vps_online",
        )

    response = _client(
        verify_vps_connect_live_proof
    ).post(
        _PATH,
        json={},
    )

    assert response.status_code == 422
    assert calls == []