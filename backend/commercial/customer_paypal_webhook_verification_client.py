"""
TODOBA Customer PayPal Webhook Verification Client

Owns only server-side PayPal webhook signature verification transport:

    PayPal transmission metadata
        + registered webhook_id
        + original webhook event
        -> PayPal verify-webhook-signature endpoint
        -> SUCCESS
        -> typed verification result

This owner deliberately does not:
- persist webhook events
- interpret capture/payment business facts
- receive payment evidence
- verify captures
- create settlement assertions
- settle payments
- grant setup activation
- mutate deployment entitlement
"""

from __future__ import annotations

from dataclasses import dataclass

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

_REQUIRED_PAYPAL_HEADERS = (
    "PAYPAL-TRANSMISSION-ID",
    "PAYPAL-TRANSMISSION-TIME",
    "PAYPAL-CERT-URL",
    "PAYPAL-AUTH-ALGO",
    "PAYPAL-TRANSMISSION-SIG",
)


@dataclass(
    frozen=True,
)
class PayPalWebhookVerificationResult:
    """
    Safe result proving PayPal verified one webhook signature.

    This is authenticity evidence only.
    It does not prove payment settlement.
    """

    webhook_event_id: str
    event_type: str
    verification_status: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "webhook_event_id",
            "event_type",
            "verification_status",
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
            self.verification_status
            != "SUCCESS"
        ):
            raise ValueError(
                "PayPal webhook signature "
                "verification did not succeed."
            )


class CustomerPayPalWebhookVerificationClient:
    """
    Verify webhook authenticity using PayPal's postback endpoint.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        webhook_id: str,
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

        self._webhook_id = (
            self._normalize_required_string(
                webhook_id,
                name="webhook_id",
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
            "CustomerPayPalWebhookVerificationClient("
            f"environment={self._environment.value!r}, "
            f"timeout_seconds={self._timeout_seconds!r}"
            ")"
        )

    def verify(
        self,
        *,
        headers: dict[str, str],
        webhook_event: dict,
    ) -> PayPalWebhookVerificationResult:
        normalized_headers = (
            self._normalize_headers(
                headers
            )
        )

        if not isinstance(
            webhook_event,
            dict,
        ):
            raise TypeError(
                "webhook_event must be dict."
            )

        webhook_event_id = (
            self._extract_webhook_identity(
                webhook_event,
                name="id",
            )
        )

        event_type = (
            self._extract_webhook_identity(
                webhook_event,
                name="event_type",
            )
        )

        access_token = (
            self._obtain_access_token()
        )

        payload = {
            "transmission_id": (
                normalized_headers[
                    "PAYPAL-TRANSMISSION-ID"
                ]
            ),
            "transmission_time": (
                normalized_headers[
                    "PAYPAL-TRANSMISSION-TIME"
                ]
            ),
            "cert_url": (
                normalized_headers[
                    "PAYPAL-CERT-URL"
                ]
            ),
            "auth_algo": (
                normalized_headers[
                    "PAYPAL-AUTH-ALGO"
                ]
            ),
            "transmission_sig": (
                normalized_headers[
                    "PAYPAL-TRANSMISSION-SIG"
                ]
            ),
            "webhook_id": (
                self._webhook_id
            ),
            "webhook_event": (
                webhook_event
            ),
        }

        url = (
            f"{self._base_url}"
            "/v1/notifications/"
            "verify-webhook-signature"
        )

        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": (
                        f"Bearer {access_token}"
                    ),
                    "Content-Type": (
                        "application/json"
                    ),
                },
                json=payload,
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(
                "PayPal webhook verification "
                "transport failed."
            ) from exc

        if response.status_code != 200:
            raise RuntimeError(
                "PayPal webhook verification "
                "request failed."
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "PayPal webhook verification "
                "response is invalid."
            ) from exc

        if not isinstance(
            body,
            dict,
        ):
            raise RuntimeError(
                "PayPal webhook verification "
                "response is invalid."
            )

        verification_status = body.get(
            "verification_status"
        )

        if (
            not isinstance(
                verification_status,
                str,
            )
            or verification_status
            != "SUCCESS"
        ):
            raise ValueError(
                "PayPal webhook signature "
                "verification failed."
            )

        return PayPalWebhookVerificationResult(
            webhook_event_id=(
                webhook_event_id
            ),
            event_type=event_type,
            verification_status=(
                verification_status
            ),
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

    @classmethod
    def _normalize_headers(
        cls,
        headers: dict[str, str],
    ) -> dict[str, str]:
        if not isinstance(
            headers,
            dict,
        ):
            raise TypeError(
                "headers must be dict."
            )

        normalized: dict[
            str,
            str,
        ] = {}

        for key, value in headers.items():
            if not isinstance(
                key,
                str,
            ):
                raise TypeError(
                    "PayPal header names must be str."
                )

            if not isinstance(
                value,
                str,
            ):
                raise TypeError(
                    "PayPal header values must be str."
                )

            normalized[
                key.strip().upper()
            ] = value.strip()

        for required in (
            _REQUIRED_PAYPAL_HEADERS
        ):
            value = normalized.get(
                required
            )

            if not value:
                raise ValueError(
                    f"Required PayPal header missing: "
                    f"{required}."
                )

        return normalized

    @staticmethod
    def _extract_webhook_identity(
        webhook_event: dict,
        *,
        name: str,
    ) -> str:
        value = webhook_event.get(
            name
        )

        if (
            not isinstance(
                value,
                str,
            )
            or not value.strip()
        ):
            raise ValueError(
                f"PayPal webhook {name} is required."
            )

        return value.strip()

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
