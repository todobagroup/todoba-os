"""
TODOBA Customer PayPal Order HTTP Client

Owns only server-side PayPal transport for:
- OAuth 2.0 client-credentials access token acquisition
- PayPal Orders v2 create-order calls
- strict response normalization into PayPalOrderCreationResult

This owner deliberately does not:
- persist PayPal order bindings
- receive payment evidence
- verify webhooks
- verify captures
- settle payments
- grant setup activation
- mutate deployment entitlement
"""

from __future__ import annotations

from enum import Enum

import httpx

from backend.commercial.customer_paypal_order_binding_service import (
    PayPalOrderCreationResult,
)


_PAYPAL_SANDBOX_BASE_URL = (
    "https://api-m.sandbox.paypal.com"
)

_PAYPAL_LIVE_BASE_URL = (
    "https://api-m.paypal.com"
)

_PAYPAL_PAYMENT_CURRENCIES = frozenset(
    {
        "AUD",
        "BRL",
        "CAD",
        "CNY",
        "CZK",
        "DKK",
        "EUR",
        "HKD",
        "HUF",
        "ILS",
        "JPY",
        "MYR",
        "MXN",
        "TWD",
        "NZD",
        "NOK",
        "PHP",
        "PLN",
        "GBP",
        "RUB",
        "SGD",
        "SEK",
        "CHF",
        "THB",
        "USD",
    }
)

_PAYPAL_ZERO_DECIMAL_CURRENCIES = frozenset(
    {
        "HUF",
        "JPY",
        "TWD",
    }
)


class PayPalEnvironment(
    str,
    Enum,
):
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"


class CustomerPayPalOrderHttpClient:
    """
    Server-side PayPal OAuth and create-order transport.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        environment: PayPalEnvironment,
        timeout_seconds: float,
    ) -> None:
        self._client_id = self._normalize_required_string(
            client_id,
            name="client_id",
        )
        self._client_secret = self._normalize_required_string(
            client_secret,
            name="client_secret",
        )

        if not isinstance(
            environment,
            PayPalEnvironment,
        ):
            raise TypeError(
                "environment must be PayPalEnvironment."
            )

        if (
            isinstance(
                timeout_seconds,
                bool,
            )
            or not isinstance(
                timeout_seconds,
                (
                    int,
                    float,
                ),
            )
        ):
            raise TypeError(
                "timeout_seconds must be numeric."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive."
            )

        self._environment = environment
        self._timeout_seconds = float(
            timeout_seconds
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerPayPalOrderHttpClient("
            f"environment={self._environment.value!r}, "
            f"timeout_seconds={self._timeout_seconds!r}"
            ")"
        )

    def create_order(
        self,
        *,
        payment_intent_id: str,
        amount_minor: int,
        currency: str,
    ) -> PayPalOrderCreationResult:
        normalized_intent_id = (
            self._normalize_required_string(
                payment_intent_id,
                name="payment_intent_id",
            )
        )

        if len(
            normalized_intent_id
        ) > 255:
            raise ValueError(
                "payment_intent_id exceeds "
                "PayPal custom_id limit."
            )

        normalized_amount = (
            self._normalize_amount_minor(
                amount_minor
            )
        )

        normalized_currency = (
            self._normalize_currency(
                currency
            )
        )

        if (
            normalized_currency
            not in _PAYPAL_PAYMENT_CURRENCIES
        ):
            raise ValueError(
                "currency is not supported "
                "for PayPal payments."
            )

        amount_value = self._format_amount(
            amount_minor=normalized_amount,
            currency=normalized_currency,
        )

        access_token = self._obtain_access_token()

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "custom_id": normalized_intent_id,
                    "amount": {
                        "currency_code": (
                            normalized_currency
                        ),
                        "value": amount_value,
                    },
                }
            ],
        }

        headers = {
            "Authorization": (
                f"Bearer {access_token}"
            ),
            "Content-Type": "application/json",
            "PayPal-Request-Id": (
                normalized_intent_id
            ),
            "Prefer": "return=representation",
        }

        url = (
            f"{self._base_url}"
            "/v2/checkout/orders"
        )

        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(
                "PayPal create order transport failed."
            ) from exc

        if response.status_code != 201:
            raise RuntimeError(
                "PayPal create order request failed."
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "PayPal order response is invalid."
            ) from exc

        return self._validate_order_response(
            body=body,
            payment_intent_id=normalized_intent_id,
            amount_minor=normalized_amount,
            currency=normalized_currency,
            amount_value=amount_value,
        )

    @property
    def _base_url(
        self,
    ) -> str:
        if (
            self._environment
            is PayPalEnvironment.SANDBOX
        ):
            return _PAYPAL_SANDBOX_BASE_URL

        return _PAYPAL_LIVE_BASE_URL

    def _obtain_access_token(
        self,
    ) -> str:
        url = (
            f"{self._base_url}"
            "/v1/oauth2/token"
        )

        try:
            response = httpx.post(
                url,
                data={
                    "grant_type": (
                        "client_credentials"
                    ),
                },
                auth=httpx.BasicAuth(
                    self._client_id,
                    self._client_secret,
                ),
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "en_US",
                },
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(
                "PayPal OAuth transport failed."
            ) from exc

        if response.status_code != 200:
            raise RuntimeError(
                "PayPal OAuth request failed."
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "PayPal OAuth response is invalid."
            ) from exc

        if not isinstance(
            body,
            dict,
        ):
            raise RuntimeError(
                "PayPal OAuth response is invalid."
            )

        access_token = body.get(
            "access_token"
        )
        token_type = body.get(
            "token_type"
        )

        if (
            not isinstance(
                access_token,
                str,
            )
            or not access_token.strip()
            or token_type != "Bearer"
        ):
            raise RuntimeError(
                "PayPal OAuth response is invalid."
            )

        return access_token.strip()

    def _validate_order_response(
        self,
        *,
        body,
        payment_intent_id: str,
        amount_minor: int,
        currency: str,
        amount_value: str,
    ) -> PayPalOrderCreationResult:
        if not isinstance(
            body,
            dict,
        ):
            raise RuntimeError(
                "PayPal order response is invalid."
            )

        paypal_order_id = body.get(
            "id"
        )

        if (
            not isinstance(
                paypal_order_id,
                str,
            )
            or not paypal_order_id.strip()
        ):
            raise RuntimeError(
                "PayPal order response is invalid."
            )

        if body.get(
            "status"
        ) != "CREATED":
            raise RuntimeError(
                "PayPal order response is invalid."
            )

        purchase_units = body.get(
            "purchase_units"
        )

        if (
            not isinstance(
                purchase_units,
                list,
            )
            or len(
                purchase_units
            ) != 1
        ):
            raise RuntimeError(
                "PayPal order response is invalid."
            )

        purchase_unit = purchase_units[
            0
        ]

        if not isinstance(
            purchase_unit,
            dict,
        ):
            raise RuntimeError(
                "PayPal order response is invalid."
            )

        if (
            purchase_unit.get(
                "custom_id"
            )
            != payment_intent_id
        ):
            raise RuntimeError(
                "PayPal order response is invalid."
            )

        amount = purchase_unit.get(
            "amount"
        )

        if not isinstance(
            amount,
            dict,
        ):
            raise RuntimeError(
                "PayPal order response is invalid."
            )

        if (
            amount.get(
                "currency_code"
            )
            != currency
            or amount.get(
                "value"
            )
            != amount_value
        ):
            raise RuntimeError(
                "PayPal order response is invalid."
            )

        return PayPalOrderCreationResult(
            paypal_order_id=(
                paypal_order_id.strip()
            ),
            paypal_request_id=(
                payment_intent_id
            ),
            custom_id=(
                payment_intent_id
            ),
            amount_minor=amount_minor,
            currency=currency,
        )

    @staticmethod
    def _format_amount(
        *,
        amount_minor: int,
        currency: str,
    ) -> str:
        if (
            currency
            in _PAYPAL_ZERO_DECIMAL_CURRENCIES
        ):
            return str(
                amount_minor
            )

        major = amount_minor // 100
        minor = amount_minor % 100

        return (
            f"{major}.{minor:02d}"
        )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} is required."
            )

        return normalized

    @staticmethod
    def _normalize_amount_minor(
        value: int,
    ) -> int:
        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int,
            )
        ):
            raise TypeError(
                "amount_minor must be int."
            )

        if value <= 0:
            raise ValueError(
                "amount_minor must be positive."
            )

        return value

    @staticmethod
    def _normalize_currency(
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "currency must be str."
            )

        normalized = (
            value.strip().upper()
        )

        if (
            len(
                normalized
            )
            != 3
            or not normalized.isascii()
            or not normalized.isalpha()
        ):
            raise ValueError(
                "currency must be a three-letter "
                "ASCII currency code."
            )

        return normalized
