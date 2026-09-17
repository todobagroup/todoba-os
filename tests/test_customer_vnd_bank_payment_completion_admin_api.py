from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationResult,
    CustomerSetupActivationStatus,
)
from backend.commercial.customer_vnd_bank_payment_completion_admin_api import (
    create_customer_vnd_bank_payment_completion_admin_router,
)


_PATH = "/internal/commercial/vnd-bank/completions"


class RecordingCompletionService:
    def __init__(self):
        self.calls = []

    def complete(
        self,
        *,
        reconciliation_id: str,
    ):
        self.calls.append(
            reconciliation_id
        )

        return CustomerSetupActivationResult(
            activation_request_id=(
                "payment-settlement-activation-settlement-001"
            ),
            setup_activation_id="setup-activation-001",
            customer_id="customer-server-owned",
            status=CustomerSetupActivationStatus.ACTIVE,
            deployment_id=None,
        )


def _build_client(
    *,
    authentication_error=None,
    completion_service=None,
):
    service = (
        completion_service
        if completion_service is not None
        else RecordingCompletionService()
    )

    def require_operator():
        if authentication_error is not None:
            raise authentication_error

        return "operator-server-owned"

    router = (
        create_customer_vnd_bank_payment_completion_admin_router(
            commercial_operator_authentication_dependency=(
                require_operator
            ),
            payment_completion_service=service,
        )
    )

    app = FastAPI()
    app.include_router(router)

    return TestClient(app), service


def test_authenticated_completion_delegates_only_reconciliation_identity():
    client, service = _build_client()

    response = client.post(
        _PATH,
        json={
            "reconciliation_id": (
                "vnd-bank-reconciliation-001"
            ),
        },
    )

    assert response.status_code == 200

    assert service.calls == [
        "vnd-bank-reconciliation-001"
    ]

    assert response.json() == {
        "setup_activation_id": "setup-activation-001",
        "status": "ACTIVE",
    }


def test_authentication_failure_blocks_completion():
    client, service = _build_client(
        authentication_error=HTTPException(
            status_code=401,
            detail=(
                "Commercial operator authentication failed."
            ),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )
    )

    response = client.post(
        _PATH,
        json={
            "reconciliation_id": (
                "vnd-bank-reconciliation-001"
            ),
        },
    )

    assert response.status_code == 401
    assert service.calls == []


def test_caller_cannot_supply_downstream_payment_or_activation_authority():
    forbidden_fields = {
        "operator_id": "operator-forged",
        "customer_id": "customer-forged",
        "order_id": "order-forged",
        "payment_intent_id": "payment-intent-forged",
        "payment_evidence_id": "payment-evidence-forged",
        "amount_minor": 1,
        "currency": "USD",
        "settlement_id": "settlement-forged",
        "activation_request_id": "activation-request-forged",
        "setup_activation_id": "setup-activation-forged",
        "activation_code": "activation-code-forged",
        "status": "ACTIVE",
        "deployment_id": "deployment-forged",
    }

    for field_name, field_value in forbidden_fields.items():
        client, service = _build_client()

        payload = {
            "reconciliation_id": (
                "vnd-bank-reconciliation-001"
            ),
            field_name: field_value,
        }

        response = client.post(
            _PATH,
            json=payload,
        )

        assert response.status_code == 422
        assert service.calls == []


def test_response_exposes_only_minimum_activation_result():
    client, _ = _build_client()

    response = client.post(
        _PATH,
        json={
            "reconciliation_id": (
                "vnd-bank-reconciliation-001"
            ),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert set(body) == {
        "setup_activation_id",
        "status",
    }

    forbidden_response_fields = (
        "activation_request_id",
        "customer_id",
        "deployment_id",
        "settlement_id",
        "payment_intent_id",
        "payment_evidence_id",
        "order_id",
        "amount_minor",
        "currency",
        "activation_code",
        "operator_id",
    )

    for field_name in forbidden_response_fields:
        assert field_name not in body


def test_router_requires_authentication_dependency():
    try:
        create_customer_vnd_bank_payment_completion_admin_router(
            commercial_operator_authentication_dependency=object(),
            payment_completion_service=(
                RecordingCompletionService()
            ),
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Non-callable authentication dependency was accepted."
        )


def test_router_requires_completion_owner():
    class NoCompletionOwner:
        pass

    try:
        create_customer_vnd_bank_payment_completion_admin_router(
            commercial_operator_authentication_dependency=(
                lambda: "operator-server-owned"
            ),
            payment_completion_service=NoCompletionOwner(),
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Completion owner without complete() was accepted."
        )
