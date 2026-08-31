"""
TODOBA Customer Setup Bootstrap HTTP Client

Customer-side transport that exchanges one trusted bootstrap
authorization code plus its PKCE verifier for one short-lived
setup launch credential.

Transport flow:

    setup_base_url
    + authorization_code
    + code_verifier
        -> POST /customer/setup/bootstrap/exchange
        -> JSON authorization_code + code_verifier
        -> HTTP 200
        -> setup_launch_credential + expires_at

Safety rules:
- no customer_id is sent or accepted
- no deployment_id, agent_id, activation, account, package,
  payment, or MT5 data is sent
- authorization code is never persisted or returned
- PKCE verifier is never persisted or returned
- authorization code and verifier are redacted from repr()
- launch credential is redacted from result repr()
- response status and schema are fail-closed
- server error bodies are never surfaced through this owner
- this owner does not issue bootstrap authorizations
- this owner does not grant launch credentials
- this owner does not read environment or runtime config
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import math
from urllib.parse import urlparse

import httpx


_BOOTSTRAP_EXCHANGE_PATH = (
    "/customer/setup/bootstrap/exchange"
)


@dataclass(
    frozen=True,
    slots=True,
)
class CustomerSetupBootstrapTransportResult:
    """
    Successful customer-side bootstrap exchange result.

    The plaintext setup launch credential must reach the
    existing setup-entry transport boundary but must not
    appear in repr().
    """

    setup_launch_credential: str = field(
        repr=False
    )
    expires_at: str

    def __post_init__(
        self,
    ) -> None:
        _require_exact_required_string(
            self.setup_launch_credential,
            name="setup_launch_credential",
        )
        _require_exact_required_string(
            self.expires_at,
            name="expires_at",
        )


class CustomerSetupBootstrapHttpClient:
    """
    Synchronous customer-side bootstrap exchange transport.
    """

    def __init__(
        self,
        *,
        setup_base_url: str,
        authorization_code: str,
        code_verifier: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        normalized_url = _normalize_base_url(
            setup_base_url
        )

        normalized_authorization_code = (
            _require_exact_required_string(
                authorization_code,
                name="authorization_code",
            )
        )

        normalized_code_verifier = (
            _require_exact_required_string(
                code_verifier,
                name="code_verifier",
            )
        )

        normalized_timeout = (
            _normalize_timeout_seconds(
                timeout_seconds
            )
        )

        self._setup_base_url = normalized_url
        self._authorization_code = (
            normalized_authorization_code
        )
        self._code_verifier = (
            normalized_code_verifier
        )
        self._timeout_seconds = (
            normalized_timeout
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupBootstrapHttpClient("
            f"setup_base_url="
            f"{self._setup_base_url!r}, "
            "authorization_code=<redacted>, "
            "code_verifier=<redacted>, "
            f"timeout_seconds="
            f"{self._timeout_seconds!r})"
        )

    def exchange(
        self,
    ) -> CustomerSetupBootstrapTransportResult:
        """
        Exchange trusted PKCE bootstrap material for one
        short-lived setup launch credential.
        """

        try:
            response = httpx.post(
                (
                    f"{self._setup_base_url}"
                    f"{_BOOTSTRAP_EXCHANGE_PATH}"
                ),
                json={
                    "authorization_code": (
                        self._authorization_code
                    ),
                    "code_verifier": (
                        self._code_verifier
                    ),
                },
                headers={
                    "Accept": "application/json",
                },
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError:
            raise RuntimeError(
                "Customer setup bootstrap request failed."
            ) from None

        if response.status_code != 200:
            raise RuntimeError(
                "Customer setup bootstrap request was "
                "rejected."
            )

        content_type = (
            response.headers.get(
                "content-type",
                "",
            )
            .split(
                ";",
                1,
            )[0]
            .strip()
            .lower()
        )

        if content_type != "application/json":
            raise RuntimeError(
                "Customer setup bootstrap response has "
                "invalid content type."
            )

        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError(
                "Customer setup bootstrap response is not "
                "valid JSON."
            ) from None

        if not isinstance(
            payload,
            dict,
        ):
            raise RuntimeError(
                "Customer setup bootstrap response has "
                "invalid schema."
            )

        if set(
            payload
        ) != {
            "setup_launch_credential",
            "expires_at",
        }:
            raise RuntimeError(
                "Customer setup bootstrap response has "
                "invalid schema."
            )

        try:
            setup_launch_credential = (
                _require_exact_required_string(
                    payload[
                        "setup_launch_credential"
                    ],
                    name=(
                        "setup_launch_credential"
                    ),
                )
            )

            expires_at = (
                _require_exact_required_string(
                    payload[
                        "expires_at"
                    ],
                    name="expires_at",
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            raise RuntimeError(
                "Customer setup bootstrap response has "
                "invalid schema."
            ) from None

        return CustomerSetupBootstrapTransportResult(
            setup_launch_credential=(
                setup_launch_credential
            ),
            expires_at=expires_at,
        )


def _normalize_base_url(
    value: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "setup_base_url must be str."
        )

    normalized = value.strip().rstrip(
        "/"
    )

    if not normalized:
        raise ValueError(
            "setup_base_url is required."
        )

    parsed = urlparse(
        normalized
    )

    if parsed.scheme not in {
        "http",
        "https",
    }:
        raise ValueError(
            "setup_base_url must use HTTP or HTTPS."
        )

    if not parsed.netloc:
        raise ValueError(
            "setup_base_url must contain a host."
        )

    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(
            "setup_base_url must not contain user info."
        )

    if (
        parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "setup_base_url must not contain query "
            "or fragment."
        )

    if parsed.path not in {
        "",
        "/",
    }:
        raise ValueError(
            "setup_base_url must not contain a path."
        )

    return normalized


def _require_exact_required_string(
    value,
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

    if (
        not value
        or value.strip() != value
    ):
        raise ValueError(
            f"{name} is invalid."
        )

    return value


def _normalize_timeout_seconds(
    value,
) -> float:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            (
                int,
                float,
            ),
        )
    ):
        raise TypeError(
            "timeout_seconds must be numeric."
        )

    normalized = float(
        value
    )

    if (
        not math.isfinite(
            normalized
        )
        or normalized <= 0
    ):
        raise ValueError(
            "timeout_seconds must be positive "
            "and finite."
        )

    return normalized
