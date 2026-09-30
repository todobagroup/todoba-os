from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)
from backend.commercial.customer_vnd_payment_initiation_api import (
    create_customer_vnd_payment_initiation_router,
)


def _customer() -> CustomerIdentity:
    return CustomerIdentity(
        customer_id="customer-p8f11b-001",
    )


def _result():
    return SimpleNamespace(
        instruction=SimpleNamespace(
            payment_intent_id="payment-intent-001",
            order_id="order-001",
            bank_code="VCB",
            account_number="123456789",
            account_name="TODOBA",
            amount_minor=927_544,
            currency="VND",
            transfer_reference="TODOBA-REF-001",
        )
    )


def _client(
    *,
    initiate,
) -> TestClient:
    customer = _customer()

    def authenticate():
        return customer

    app = FastAPI()

    app.include_router(
        create_customer_vnd_payment_initiation_router(
            initiate_vnd_payment=initiate,
            customer_authentication_dependency=authenticate,
        )
    )

    return TestClient(app)


def test_authenticated_customer_can_initiate_vnd_payment():
    captured = {}

    def initiate(
        *,
        initiation_request_id,
        authenticated_customer,
    ):
        captured[
            "initiation_request_id"
        ] = initiation_request_id
        captured[
            "customer_id"
        ] = authenticated_customer.customer_id

        return _result()

    client = _client(
        initiate=initiate
    )

    response = client.post(
        "/customer/payments/vnd/initiate",
        json={
            "initiation_request_id": (
                "initiation-request-001"
            )
        },
    )

    assert response.status_code == 200

    assert captured == {
        "initiation_request_id": (
            "initiation-request-001"
        ),
        "customer_id": (
            "customer-p8f11b-001"
        ),
    }

    assert response.json() == {
        "payment_intent_id": "payment-intent-001",
        "order_id": "order-001",
        "bank_code": "VCB",
        "account_number": "123456789",
        "account_name": "TODOBA",
        "amount_minor": 927_544,
        "currency": "VND",
        "transfer_reference": "TODOBA-REF-001",
    }

    assert (
        response.headers["cache-control"]
        == "no-store"
    )

    assert (
        response.headers["pragma"]
        == "no-cache"
    )


def test_http_request_forbids_client_monetary_authority():
    client = _client(
        initiate=lambda **_: _result()
    )

    forbidden_payloads = (
        {"customer_id": "attacker"},
        {
            "authoritative_cycle_balance_usd": (
                "100000"
            )
        },
        {"licensed_account_cap_usd": 100000},
        {"usd_price": "35"},
        {"amount_minor": 1},
        {"currency": "USD"},
        {"payment_rail": "paypal"},
        {"payment_intent_id": "forged"},
        {"bank_code": "FAKE"},
        {"account_number": "000"},
        {"account_name": "ATTACKER"},
    )

    for extra in forbidden_payloads:
        payload = {
            "initiation_request_id": (
                "initiation-request-002"
            )
        }

        payload.update(
            extra
        )

        response = client.post(
            "/customer/payments/vnd/initiate",
            json=payload,
        )

        assert response.status_code == 422


def test_http_boundary_rejects_empty_request_identity():
    client = _client(
        initiate=lambda **_: _result()
    )

    response = client.post(
        "/customer/payments/vnd/initiate",
        json={
            "initiation_request_id": "   "
        },
    )

    assert response.status_code == 422


def test_authoritative_unavailable_state_fails_closed():
    def initiate(**_):
        raise RuntimeError(
            "Authoritative current billing cycle "
            "is not configured."
        )

    client = _client(
        initiate=initiate
    )

    response = client.post(
        "/customer/payments/vnd/initiate",
        json={
            "initiation_request_id": (
                "initiation-request-003"
            )
        },
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": (
            "VND payment initiation is "
            "not currently available."
        )
    }

    assert (
        response.headers["cache-control"]
        == "no-store"
    )


def test_unexpected_internal_failure_is_generic():
    def initiate(**_):
        raise TypeError(
            "secret internal detail"
        )

    client = _client(
        initiate=initiate
    )

    response = client.post(
        "/customer/payments/vnd/initiate",
        json={
            "initiation_request_id": (
                "initiation-request-004"
            )
        },
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail": (
            "VND payment initiation "
            "could not be completed."
        )
    }

    assert "secret internal detail" not in response.text


def test_http_owner_has_no_settlement_or_activation_authority():
    from pathlib import Path

    source = Path(
        "backend/commercial/"
        "customer_vnd_payment_initiation_api.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "CustomerPaymentSettlementService",
        "CustomerVndBankReconciliationService",
        "CustomerCommercialEntitlementRegistry",
        "CustomerSetupActivationService",
    )

    for token in forbidden:
        assert token not in source
