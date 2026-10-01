import importlib

import pytest

import backend.config as config
from backend.commercial.customer_paypal_order_http_client import (
    PayPalEnvironment,
)


_ENV_NAMES = (
    "TODOBA_PAYPAL_CLIENT_ID",
    "TODOBA_PAYPAL_CLIENT_SECRET",
    "TODOBA_PAYPAL_WEBHOOK_ID",
    "TODOBA_PAYPAL_ENVIRONMENT",
    "TODOBA_PAYPAL_TIMEOUT_SECONDS",
)


def _reload(
    monkeypatch,
    *,
    client_id="paypal-client-id",
    client_secret="paypal-client-secret",
    webhook_id="paypal-webhook-id",
    environment="LIVE",
    timeout_seconds="10.0",
):
    values = {
        "TODOBA_PAYPAL_CLIENT_ID": client_id,
        "TODOBA_PAYPAL_CLIENT_SECRET": client_secret,
        "TODOBA_PAYPAL_WEBHOOK_ID": webhook_id,
        "TODOBA_PAYPAL_ENVIRONMENT": environment,
        "TODOBA_PAYPAL_TIMEOUT_SECONDS": timeout_seconds,
    }

    for name in _ENV_NAMES:
        monkeypatch.delenv(
            name,
            raising=False,
        )

    for name, value in values.items():
        monkeypatch.setenv(
            name,
            value,
        )

    return importlib.reload(
        config
    )


def test_paypal_runtime_config_returns_typed_server_credentials(
    monkeypatch,
):
    loaded = _reload(
        monkeypatch,
        client_id="  paypal-client-id  ",
        client_secret="paypal-client-secret",
        webhook_id="  paypal-webhook-id  ",
        environment="live",
        timeout_seconds="12.5",
    )

    (
        client_id,
        client_secret,
        webhook_id,
        environment,
        timeout_seconds,
    ) = loaded.get_paypal_runtime_config()

    assert client_id == "paypal-client-id"
    assert client_secret == "paypal-client-secret"
    assert webhook_id == "paypal-webhook-id"
    assert environment is PayPalEnvironment.LIVE
    assert timeout_seconds == 12.5


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "expected",
    ),
    [
        (
            "client_id",
            "",
            "TODOBA_PAYPAL_CLIENT_ID is required",
        ),
        (
            "client_secret",
            "   ",
            "TODOBA_PAYPAL_CLIENT_SECRET is required",
        ),
        (
            "webhook_id",
            "",
            "TODOBA_PAYPAL_WEBHOOK_ID is required",
        ),
    ],
)
def test_paypal_runtime_config_fails_closed_when_required_value_missing(
    monkeypatch,
    field,
    value,
    expected,
):
    kwargs = {
        field: value,
    }

    loaded = _reload(
        monkeypatch,
        **kwargs,
    )

    with pytest.raises(
        RuntimeError,
        match=expected,
    ):
        loaded.get_paypal_runtime_config()


def test_paypal_runtime_config_rejects_unknown_environment(
    monkeypatch,
):
    loaded = _reload(
        monkeypatch,
        environment="PRODUCTIONISH",
    )

    with pytest.raises(
        RuntimeError,
        match="TODOBA_PAYPAL_ENVIRONMENT",
    ):
        loaded.get_paypal_runtime_config()


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        "0",
        "-1",
    ],
)
def test_paypal_runtime_config_requires_positive_timeout(
    monkeypatch,
    timeout_seconds,
):
    loaded = _reload(
        monkeypatch,
        timeout_seconds=timeout_seconds,
    )

    with pytest.raises(
        RuntimeError,
        match="TODOBA_PAYPAL_TIMEOUT_SECONDS",
    ):
        loaded.get_paypal_runtime_config()


def test_paypal_runtime_config_secret_is_not_exposed_by_error(
    monkeypatch,
):
    secret = "paypal-super-secret-value"

    loaded = _reload(
        monkeypatch,
        client_id="",
        client_secret=secret,
    )

    with pytest.raises(
        RuntimeError
    ) as exc_info:
        loaded.get_paypal_runtime_config()

    assert secret not in str(
        exc_info.value
    )
