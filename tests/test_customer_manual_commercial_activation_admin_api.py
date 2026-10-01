from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_manual_commercial_activation_admin_api import (
    create_customer_manual_commercial_activation_admin_router,
)


_PATH = "/internal/commercial/manual-activations"


class RecordingManualActivationService:
    def __init__(self):
        self.calls = []

    def approve(
        self,
        *,
        manual_approval_request_id,
        registration_request_id,
        operator_id,
    ):
        self.calls.append(
            (
                manual_approval_request_id,
                registration_request_id,
                operator_id,
            )
        )

        from backend.commercial.customer_manual_commercial_activation_service import (
            CustomerManualCommercialActivationResult,
        )

        return CustomerManualCommercialActivationResult(
            manual_approval_request_id=(
                manual_approval_request_id
            ),
            registration_request_id=(
                registration_request_id
            ),
            operator_id=operator_id,
            customer_id="customer-authoritative-001",
            setup_activation_id=(
                "setup-activation-manual-001"
            ),
        )


def _client(
    *,
    authentication_error=None,
):
    service = RecordingManualActivationService()

    def require_operator():
        if authentication_error is not None:
            raise authentication_error

        return "operator-server-owned"

    router = (
        create_customer_manual_commercial_activation_admin_router(
            commercial_operator_authentication_dependency=(
                require_operator
            ),
            manual_activation_service=service,
        )
    )

    app = FastAPI()
    app.include_router(router)

    return TestClient(app), service


def test_authenticated_operator_approves_by_registration_identity():
    client, service = _client()

    response = client.post(
        _PATH,
        json={
            "manual_approval_request_id": "manual-sale-001",
            "registration_request_id": "registration-001",
        },
    )

    assert response.status_code == 200

    assert service.calls == [
        (
            "manual-sale-001",
            "registration-001",
            "operator-server-owned",
        )
    ]

    assert response.json() == {
        "manual_approval_request_id": "manual-sale-001",
        "registration_request_id": "registration-001",
        "customer_id": "customer-authoritative-001",
        "setup_activation_id": "setup-activation-manual-001",
    }


def test_caller_cannot_supply_authority_fields():
    forbidden = {
        "operator_id": "operator-forged",
        "customer_id": "customer-forged",
        "payment_intent_id": "payment-forged",
        "settlement_id": "settlement-forged",
        "amount_minor": 1,
        "currency": "VND",
        "activation_code": "forged-code",
        "setup_activation_id": "forged-activation",
        "status": "ACTIVE",
    }

    for field_name, value in forbidden.items():
        client, service = _client()

        response = client.post(
            _PATH,
            json={
                "manual_approval_request_id": "manual-sale-001",
                "registration_request_id": "registration-001",
                field_name: value,
            },
        )

        assert response.status_code == 422
        assert service.calls == []


def test_response_does_not_expose_operator_or_access_code():
    client, _ = _client()

    response = client.post(
        _PATH,
        json={
            "manual_approval_request_id": "manual-sale-001",
            "registration_request_id": "registration-001",
        },
    )

    assert response.status_code == 200

    assert "operator_id" not in response.json()
    assert "activation_code" not in response.json()
