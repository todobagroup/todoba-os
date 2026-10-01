from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_paypal_verified_capture_ingress_api import (
    create_customer_paypal_verified_capture_ingress_router,
)


_PATH = "/commercial/paypal/webhook"


class RecordingIngressService:
    def __init__(self):
        self.calls = []

    def complete(
        self,
        *,
        headers,
        webhook_event,
    ):
        self.calls.append(
            (
                headers,
                webhook_event,
            )
        )

        return SimpleNamespace(
            setup_activation_id="setup-activation-paypal-001",
            customer_id="customer-001",
        )


def _client():
    service = RecordingIngressService()

    app = FastAPI()

    app.include_router(
        create_customer_paypal_verified_capture_ingress_router(
            ingress_service=service
        )
    )

    return TestClient(app), service


def _event():
    return {
        "id": "WH-EVENT-001",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAPTURE-001",
        },
    }


def _paypal_headers():
    return {
        "PAYPAL-TRANSMISSION-ID": "transmission-001",
        "PAYPAL-TRANSMISSION-TIME": "2026-10-01T00:00:00Z",
        "PAYPAL-CERT-URL": "https://api.paypal.com/cert.pem",
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-TRANSMISSION-SIG": "signature",
    }


def test_webhook_api_passes_only_headers_and_original_event():
    client, service = _client()

    response = client.post(
        _PATH,
        headers=_paypal_headers(),
        json=_event(),
    )

    assert response.status_code == 200
    assert len(service.calls) == 1

    headers, event = service.calls[0]

    assert event == _event()

    normalized = {
        key.lower(): value
        for key, value in headers.items()
    }

    assert (
        normalized["paypal-transmission-id"]
        == "transmission-001"
    )


def test_webhook_api_response_exposes_no_payment_or_secret_truth():
    client, _ = _client()

    response = client.post(
        _PATH,
        headers=_paypal_headers(),
        json=_event(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body == {
        "status": "accepted"
    }

    for forbidden in (
        "customer_id",
        "setup_activation_id",
        "payment_intent_id",
        "order_id",
        "capture_id",
        "activation_code",
        "client_secret",
        "webhook_id",
    ):
        assert forbidden not in body


def test_webhook_api_accepts_no_caller_payment_authority_fields():
    client, service = _client()

    event = _event()

    event.update(
        {
            "customer_id": "forged",
            "payment_intent_id": "forged",
            "order_id": "forged",
            "amount_minor": 1,
            "currency": "XXX",
        }
    )

    response = client.post(
        _PATH,
        headers=_paypal_headers(),
        json=event,
    )

    assert response.status_code == 200
    assert len(service.calls) == 1
