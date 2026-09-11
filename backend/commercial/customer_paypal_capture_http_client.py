"""
TODOBA Customer PayPal Capture HTTP Client

Owns only server-side PayPal capture-details transport:

    capture_id
        -> OAuth 2.0 client credentials
        -> GET PayPal capture details
        -> strict provider fact validation
        -> PayPalCaptureDetails

This owner deliberately does not:
- persist capture details
- create payment evidence
- bind PayPal orders
- verify webhook signatures
- create settlement assertions
- settle payments
- grant activation
"""

from __future__ import annotations

from dataclasses import dataclass
import re

import httpx

from backend.commercial.customer_paypal_order_http_client import (
    PayPalEnvironment,
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

_TWO_DECIMAL_AMOUNT_RE = re.compile(
    r"^[0-9]+\.[0-9]{2}$"
)

_ZERO_DECIMAL_AMOUNT_RE = re.compile(
    r"^[0-9]+$"
)


@dataclass(
    frozen=True,
)
class PayPalCaptureDetails:
    capture_id: str
    order_id: str
    custom_id: str
    amount_minor: int
    currency: str
    status: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "capture_id",
            "order_id",
            "custom_id",
        ):
            value = getattr(
                self,
                name,
            )

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

            object.__setattr__(
                self,
                name,
                normalized,
            )

        if (
            isinstance(
                self.amount_minor,
                bool,
            )
            or not isinstance(
                self.amount_minor,
                int,
            )
        ):
            raise TypeError(
                "amount_minor must be int."
            )

        if self.amount_minor <= 0:
            raise ValueError(
                "amount_minor must be positive."
            )

        if not isinstance(
            self.currency,
            str,
        ):
            raise TypeError(
                "currency must be str."
            )

        normalized_currency = (
            self.currency.strip().upper()
        )

        if (
            len(
                normalized_currency
            )
            != 3
            or not normalized_currency.isascii()
            or not normalized_currency.isalpha()
        ):
            raise ValueError(
                "currency must be a three-letter "
                "ASCII currency code."
            )

        if (
            normalized_currency
            not in _PAYPAL_PAYMENT_CURRENCIES
        ):
            raise ValueError(
                "currency is not supported "
                "for PayPal payments."
            )

        object.__setattr__(
            self,
            "currency",
            normalized_currency,
        )

        if not isinstance(
            self.status,
            str,
        ):
            raise TypeError(
                "status must be str."
            )

        normalized_status = (
            self.status.strip()
        )

        if (
            normalized_status
            != "COMPLETED"
        ):
            raise ValueError(
                "PayPal capture status must be COMPLETED."
            )

        object.__setattr__(
            self,
            "status",
            normalized_status,
        )


class CustomerPayPalCaptureHttpClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        environment: PayPalEnvironment,
        timeout_seconds: float,
    ) -> None:
        self._client_id = (
            self._normalize_required_string(
                client_id,
                name="client_id",
            )
        )

        self._client_secret = (
            self._normalize_required_string(
                client_secret,
                name="client_secret",
            )
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
            "CustomerPayPalCaptureHttpClient("
            f"environment={self._environment.value!r}, "
            f"timeout_seconds={self._timeout_seconds!r}"
            ")"
        )

    def get_capture(
        self,
        *,
        capture_id: str,
    ) -> PayPalCaptureDetails:
        normalized_capture_id = (
            self._normalize_required_string(
                capture_id,
                name="capture_id",
            )
        )

        access_token = (
            self._obtain_access_token()
        )

        url = (
            f"{self._base_url}"
            "/v2/payments/captures/"
            f"{normalized_capture_id}"
        )

        try:
            response = httpx.get(
                url,
                headers={
                    "Authorization": (
                        f"Bearer {access_token}"
                    ),
                    "Accept": "application/json",
                },
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(
                "PayPal capture transport failed."
            ) from exc

        if response.status_code != 200:
            raise RuntimeError(
                "PayPal capture request failed."
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "PayPal capture response is invalid."
            ) from exc

        return self._parse_capture(
            requested_capture_id=(
                normalized_capture_id
            ),
            body=body,
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

    def _parse_capture(
        self,
        *,
        requested_capture_id: str,
        body,
    ) -> PayPalCaptureDetails:
        if not isinstance(
            body,
            dict,
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        capture_id = body.get(
            "id"
        )

        if (
            not isinstance(
                capture_id,
                str,
            )
            or not capture_id.strip()
            or capture_id.strip()
            != requested_capture_id
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        status = body.get(
            "status"
        )

        if (
            not isinstance(
                status,
                str,
            )
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        if status.strip() != "COMPLETED":
            raise ValueError(
                "PayPal capture status must be COMPLETED."
            )

        custom_id = body.get(
            "custom_id"
        )

        if (
            not isinstance(
                custom_id,
                str,
            )
            or not custom_id.strip()
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        amount = body.get(
            "amount"
        )

        if not isinstance(
            amount,
            dict,
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        currency = amount.get(
            "currency_code"
        )
        value = amount.get(
            "value"
        )

        amount_minor = (
            self._parse_amount_minor(
                currency=currency,
                value=value,
            )
        )

        supplementary_data = body.get(
            "supplementary_data"
        )

        if not isinstance(
            supplementary_data,
            dict,
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        related_ids = supplementary_data.get(
            "related_ids"
        )

        if not isinstance(
            related_ids,
            dict,
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        order_id = related_ids.get(
            "order_id"
        )

        if (
            not isinstance(
                order_id,
                str,
            )
            or not order_id.strip()
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        try:
            return PayPalCaptureDetails(
                capture_id=capture_id,
                order_id=order_id,
                custom_id=custom_id,
                amount_minor=amount_minor,
                currency=currency,
                status=status,
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "PayPal capture response is invalid."
            ) from exc

    @staticmethod
    def _parse_amount_minor(
        *,
        currency,
        value,
    ) -> int:
        if not isinstance(
            currency,
            str,
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        normalized_currency = (
            currency.strip().upper()
        )

        if (
            normalized_currency
            not in _PAYPAL_PAYMENT_CURRENCIES
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        if not isinstance(
            value,
            str,
        ):
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        normalized_value = value.strip()

        if (
            normalized_currency
            in _PAYPAL_ZERO_DECIMAL_CURRENCIES
        ):
            if (
                _ZERO_DECIMAL_AMOUNT_RE.fullmatch(
                    normalized_value
                )
                is None
            ):
                raise RuntimeError(
                    "PayPal capture response is invalid."
                )

            amount_minor = int(
                normalized_value
            )

        else:
            if (
                _TWO_DECIMAL_AMOUNT_RE.fullmatch(
                    normalized_value
                )
                is None
            ):
                raise RuntimeError(
                    "PayPal capture response is invalid."
                )

            major_text, minor_text = (
                normalized_value.split(
                    ".",
                    1,
                )
            )

            amount_minor = (
                int(
                    major_text
                )
                * 100
                + int(
                    minor_text
                )
            )

        if amount_minor <= 0:
            raise RuntimeError(
                "PayPal capture response is invalid."
            )

        return amount_minor

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
