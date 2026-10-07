import ast
from pathlib import Path

import httpx
import pytest

from backend.commercial import (
    customer_paypal_order_http_client as order_module,
)
from backend.commercial.customer_paypal_checkout_experience_api import (
    create_customer_paypal_checkout_experience_router,
)
from backend.commercial.customer_paypal_order_http_client import (
    CustomerPayPalOrderHttpClient,
    PayPalEnvironment,
)


RETURN_URL = (
    "https://api.todobagroup.com"
    "/commercial/paypal/return"
)

CANCEL_URL = (
    "https://api.todobagroup.com"
    "/commercial/paypal/cancel"
)


def _response(
    status_code,
    payload,
    *,
    url,
):
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request(
            "POST",
            url,
        ),
    )


def test_create_order_emits_direct_pay_now_experience(
    monkeypatch,
):
    calls = []

    def fake_post(
        url,
        **kwargs,
    ):
        calls.append(
            (
                url,
                kwargs,
            )
        )

        if url.endswith(
            "/v1/oauth2/token"
        ):
            return _response(
                200,
                {
                    "access_token": "token",
                    "token_type": "Bearer",
                },
                url=url,
            )

        return _response(
            201,
            {
                "id": "PAYPAL-ORDER-001",
                "status": "CREATED",
                "purchase_units": [
                    {
                        "custom_id": (
                            "payment-intent-001"
                        ),
                        "amount": {
                            "currency_code": "USD",
                            "value": "140.00",
                        },
                    }
                ],
                "links": [
                    {
                        "href": (
                            "https://www.sandbox.paypal.com/"
                            "checkoutnow?token="
                            "PAYPAL-ORDER-001"
                        ),
                        "rel": "approve",
                        "method": "GET",
                    }
                ],
            },
            url=url,
        )

    monkeypatch.setattr(
        order_module.httpx,
        "post",
        fake_post,
    )

    client = CustomerPayPalOrderHttpClient(
        client_id="client",
        client_secret="secret",
        environment=PayPalEnvironment.SANDBOX,
        timeout_seconds=10.0,
        checkout_return_url=RETURN_URL,
        checkout_cancel_url=CANCEL_URL,
    )

    client.create_order(
        payment_intent_id="payment-intent-001",
        amount_minor=14000,
        currency="USD",
    )

    payload = calls[1][1][
        "json"
    ]

    assert payload[
        "payment_source"
    ] == {
        "paypal": {
            "experience_context": {
                "user_action": "PAY_NOW",
                "shipping_preference": (
                    "NO_SHIPPING"
                ),
                "return_url": RETURN_URL,
                "cancel_url": CANCEL_URL,
            }
        }
    }


def test_checkout_urls_must_be_provided_as_pair():
    with pytest.raises(
        ValueError,
        match="provided together",
    ):
        CustomerPayPalOrderHttpClient(
            client_id="client",
            client_secret="secret",
            environment=PayPalEnvironment.SANDBOX,
            timeout_seconds=10.0,
            checkout_return_url=RETURN_URL,
        )


@pytest.mark.parametrize(
    "bad_url",
    (
        "",
        "ftp://api.todobagroup.com/return",
        "not-a-url",
    ),
)
def test_checkout_urls_require_http_or_https(
    bad_url,
):
    with pytest.raises(
        ValueError,
    ):
        CustomerPayPalOrderHttpClient(
            client_id="client",
            client_secret="secret",
            environment=PayPalEnvironment.SANDBOX,
            timeout_seconds=10.0,
            checkout_return_url=bad_url,
            checkout_cancel_url=CANCEL_URL,
        )


def test_capture_transport_does_not_require_checkout_ux():
    client = CustomerPayPalOrderHttpClient(
        client_id="client",
        client_secret="secret",
        environment=PayPalEnvironment.SANDBOX,
        timeout_seconds=10.0,
    )

    assert client is not None


def test_checkout_landing_routes_are_get_only():
    router = (
        create_customer_paypal_checkout_experience_router()
    )

    routes = {
        route.path: route
        for route in router.routes
    }

    assert set(
        routes
    ) == {
        "/commercial/paypal/return",
        "/commercial/paypal/cancel",
    }

    for route in routes.values():
        assert route.methods == {
            "GET",
        }


def test_checkout_landings_do_not_claim_payment_truth():
    router = (
        create_customer_paypal_checkout_experience_router()
    )

    routes = {
        route.path: route
        for route in router.routes
    }

    return_response = routes[
        "/commercial/paypal/return"
    ].endpoint()

    cancel_response = routes[
        "/commercial/paypal/cancel"
    ].endpoint()

    assert return_response.status_code == 200
    assert cancel_response.status_code == 200

    return_body = (
        return_response.body
        .decode("utf-8")
        .lower()
    )

    cancel_body = (
        cancel_response.body
        .decode("utf-8")
        .lower()
    )

    assert "approval received" in return_body
    assert "securely verified" in return_body
    assert "no payment confirmation" in cancel_body

    for body in (
        return_body,
        cancel_body,
    ):
        assert "settlement id" not in body
        assert "activation code" not in body
        assert "payment completed" not in body


def _function_source(
    name,
):
    path = Path(
        "backend/main.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    matches = [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == name
        )
    ]

    assert len(
        matches
    ) == 1

    return ast.get_source_segment(
        source,
        matches[0],
    )


def test_production_initiation_owns_checkout_ux_config():
    source = _function_source(
        "_compose_customer_paypal_payment_initiation_runtime"
    )

    assert "TODOBA_CLOUD_BASE_URL" in source
    assert "checkout_return_url" in source
    assert "checkout_cancel_url" in source

    assert (
        "create_customer_paypal_checkout_experience_router"
        in source
    )


def test_capture_execution_does_not_own_checkout_ux_config():
    source = _function_source(
        "_compose_customer_paypal_capture_execution_runtime"
    )

    assert "checkout_return_url" not in source
    assert "checkout_cancel_url" not in source
    assert (
        "create_customer_paypal_checkout_experience_router"
        not in source
    )


def test_checkout_api_has_no_payment_truth_calls():
    source = Path(
        "backend/commercial/"
        "customer_paypal_checkout_experience_api.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "complete_verified_payment(",
        "receive_evidence(",
        "capture_order(",
        "activate_from_settlement(",
        ".settle(",
        ".activate(",
    )

    for token in forbidden:
        assert token not in source


def test_direct_checkout_accepts_provider_payer_action_contract(
    monkeypatch,
):
    calls = []

    def fake_post(
        url,
        **kwargs,
    ):
        calls.append(
            (
                url,
                kwargs,
            )
        )

        if url.endswith(
            "/v1/oauth2/token"
        ):
            return _response(
                200,
                {
                    "access_token": "token",
                    "token_type": "Bearer",
                },
                url=url,
            )

        assert url.endswith(
            "/v2/checkout/orders"
        )

        return _response(
            200,
            {
                "id": "PAYPAL-ORDER-PAYER-ACTION",
                "intent": "CAPTURE",
                "status": "PAYER_ACTION_REQUIRED",
                "payment_source": {
                    "paypal": {},
                },
                "purchase_units": [
                    {
                        "reference_id": "default",
                        "custom_id": (
                            "payment-intent-payer-action"
                        ),
                        "amount": {
                            "currency_code": "USD",
                            "value": "140.00",
                        },
                    }
                ],
                "links": [
                    {
                        "href": (
                            "https://www.sandbox.paypal.com/"
                            "checkoutnow?token="
                            "PAYPAL-ORDER-PAYER-ACTION"
                        ),
                        "rel": "payer-action",
                        "method": "GET",
                    }
                ],
            },
            url=url,
        )

    monkeypatch.setattr(
        order_module.httpx,
        "post",
        fake_post,
    )

    client = CustomerPayPalOrderHttpClient(
        client_id="client-id",
        client_secret="client-secret",
        environment=PayPalEnvironment.SANDBOX,
        timeout_seconds=10.0,
        checkout_return_url=(
            "https://api.todobagroup.com/"
            "commercial/paypal/return"
        ),
        checkout_cancel_url=(
            "https://api.todobagroup.com/"
            "commercial/paypal/cancel"
        ),
    )

    result = client.create_order(
        payment_intent_id=(
            "payment-intent-payer-action"
        ),
        amount_minor=14000,
        currency="USD",
    )

    assert result.paypal_order_id == (
        "PAYPAL-ORDER-PAYER-ACTION"
    )

    assert result.paypal_request_id == (
        "payment-intent-payer-action"
    )

    assert result.custom_id == (
        "payment-intent-payer-action"
    )

    assert result.amount_minor == 14000
    assert result.currency == "USD"

    assert result.approval_url == (
        "https://www.sandbox.paypal.com/"
        "checkoutnow?token="
        "PAYPAL-ORDER-PAYER-ACTION"
    )

    assert len(calls) == 2
