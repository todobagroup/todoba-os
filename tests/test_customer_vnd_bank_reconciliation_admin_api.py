from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.commercial.customer_vnd_bank_reconciliation_service import (
    CustomerVndBankReconciliationRecord,
    CustomerVndBankReconciliationStatus,
)
from backend.commercial.customer_vnd_bank_reconciliation_admin_api import (
    create_customer_vnd_bank_reconciliation_admin_router,
)


_PATH = "/internal/commercial/vnd-bank/reconciliations"


class RecordingReconciliationService:
    def __init__(self):
        self.calls = []

    def confirm(
        self,
        *,
        reconciliation_request_id,
        payment_intent_id,
        bank_reference,
        amount_minor,
        currency,
        operator_id,
    ):
        self.calls.append(
            {
                "reconciliation_request_id": reconciliation_request_id,
                "payment_intent_id": payment_intent_id,
                "bank_reference": bank_reference,
                "amount_minor": amount_minor,
                "currency": currency,
                "operator_id": operator_id,
            }
        )

        return CustomerVndBankReconciliationRecord(
            reconciliation_request_id=reconciliation_request_id,
            reconciliation_id="vnd-bank-reconciliation-001",
            payment_intent_id=payment_intent_id,
            order_id="order-001",
            customer_id="customer-001",
            bank_reference=bank_reference,
            amount_minor=amount_minor,
            currency=currency,
            operator_id=operator_id,
            status=CustomerVndBankReconciliationStatus.CONFIRMED,
        )


def _build_client(
    *,
    authenticated_operator_id="operator-founder",
    authentication_error=None,
):
    service = RecordingReconciliationService()

    def require_operator():
        if authentication_error is not None:
            raise authentication_error

        return authenticated_operator_id

    router = create_customer_vnd_bank_reconciliation_admin_router(
        commercial_operator_authentication_dependency=require_operator,
        reconciliation_service=service,
    )

    app = FastAPI()
    app.include_router(router)

    return TestClient(app), service


def _valid_payload():
    return {
        "reconciliation_request_id": "reconcile-request-001",
        "payment_intent_id": "payment-intent-001",
        "bank_reference": "VCB-20260913-000001",
        "amount_minor": 2500000,
    }


def test_authenticated_operator_confirms_vnd_reconciliation():
    client, service = _build_client()

    response = client.post(
        _PATH,
        json=_valid_payload(),
    )

    assert response.status_code == 200

    assert response.json() == {
        "reconciliation_request_id": "reconcile-request-001",
        "reconciliation_id": "vnd-bank-reconciliation-001",
        "status": "CONFIRMED",
    }

    assert service.calls == [
        {
            "reconciliation_request_id": "reconcile-request-001",
            "payment_intent_id": "payment-intent-001",
            "bank_reference": "VCB-20260913-000001",
            "amount_minor": 2500000,
            "currency": "VND",
            "operator_id": "operator-founder",
        }
    ]


def test_operator_identity_comes_only_from_authentication_dependency():
    client, service = _build_client(
        authenticated_operator_id="operator-server-owned"
    )

    response = client.post(
        _PATH,
        json=_valid_payload(),
    )

    assert response.status_code == 200
    assert service.calls[0]["operator_id"] == "operator-server-owned"


def test_authentication_failure_blocks_reconciliation():
    client, service = _build_client(
        authentication_error=HTTPException(
            status_code=401,
            detail="Commercial operator authentication failed.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )
    )

    response = client.post(
        _PATH,
        json=_valid_payload(),
    )

    assert response.status_code == 401
    assert service.calls == []


def test_caller_cannot_supply_operator_identity():
    client, service = _build_client()

    payload = _valid_payload()
    payload["operator_id"] = "operator-forged"

    response = client.post(
        _PATH,
        json=payload,
    )

    assert response.status_code == 422
    assert service.calls == []


def test_caller_cannot_supply_customer_or_order_identity():
    for forbidden_field in (
        "customer_id",
        "order_id",
    ):
        client, service = _build_client()

        payload = _valid_payload()
        payload[forbidden_field] = "caller-controlled"

        response = client.post(
            _PATH,
            json=payload,
        )

        assert response.status_code == 422
        assert service.calls == []


def test_currency_is_server_owned_vnd_not_request_authority():
    client, service = _build_client()

    payload = _valid_payload()
    payload["currency"] = "USD"

    response = client.post(
        _PATH,
        json=payload,
    )

    assert response.status_code == 422
    assert service.calls == []


def test_caller_cannot_supply_reconciliation_result_fields():
    for forbidden_field in (
        "reconciliation_id",
        "status",
    ):
        client, service = _build_client()

        payload = _valid_payload()
        payload[forbidden_field] = "FORGED"

        response = client.post(
            _PATH,
            json=payload,
        )

        assert response.status_code == 422
        assert service.calls == []


def test_router_requires_authentication_dependency():
    try:
        create_customer_vnd_bank_reconciliation_admin_router(
            commercial_operator_authentication_dependency=object(),
            reconciliation_service=RecordingReconciliationService(),
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Non-callable authentication dependency was accepted."
        )


def test_router_requires_reconciliation_confirm_owner():
    class NoConfirmOwner:
        pass

    try:
        create_customer_vnd_bank_reconciliation_admin_router(
            commercial_operator_authentication_dependency=lambda: (
                "operator-founder"
            ),
            reconciliation_service=NoConfirmOwner(),
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "Reconciliation owner without confirm() was accepted."
        )


def test_api_boundary_exposes_no_downstream_payment_authority():
    client, service = _build_client()

    response = client.post(
        _PATH,
        json=_valid_payload(),
    )

    assert response.status_code == 200

    forbidden_methods = (
        "publish",
        "receive",
        "build_assertion",
        "verify_payment",
        "settle",
        "mark_paid",
        "activate_from_settlement",
        "activate_setup",
        "activate_entitlement",
    )

    for method_name in forbidden_methods:
        assert not hasattr(
            service,
            method_name,
        )
