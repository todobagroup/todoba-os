import pytest

import backend.commercial.customer_setup_access_code_http_client as access_code_http_client_module

from backend.commercial.customer_setup_access_code_http_client import (
    CustomerSetupAccessCodeHttpClient,
)


_EXPECTED_USER_AGENT = (
    "TODOBA-Trading-AI-Setup/1.0"
)


def test_activation_exchange_sends_product_user_agent(
    monkeypatch,
):
    captured = {}

    def fake_urlopen(
        request,
        *,
        timeout,
    ):
        captured["request"] = request
        captured["timeout"] = timeout

        raise RuntimeError(
            "stop-after-request-capture"
        )

    monkeypatch.setattr(
        access_code_http_client_module,
        "urlopen",
        fake_urlopen,
    )

    client = CustomerSetupAccessCodeHttpClient(
        setup_base_url=(
            "https://api.todobagroup.com"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="stop-after-request-capture",
    ):
        client.exchange(
            activation_code=(
                "customer-activation-code"
            ),
            code_challenge_s256=(
                "A" * 43
            ),
        )

    request = captured["request"]

    assert (
        request.get_header(
            "User-agent"
        )
        == _EXPECTED_USER_AGENT
    )

    assert (
        request.get_header(
            "Content-type"
        )
        == "application/json"
    )

    assert (
        request.get_header(
            "Accept"
        )
        == "application/json"
    )