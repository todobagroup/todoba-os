"""
Customer-side HTTP transport for TODOBA Setup Activation Code exchange.

The customer supplies:
- one opaque Activation Code
- one public PKCE S256 challenge generated locally by Setup

The server returns:
- one short-lived internal bootstrap authorization code
- its expiry

Security boundaries:
- customer_id and setup_activation_id never cross this client API
- plaintext Activation Code and authorization code are never persisted
- secrets are never included in repr() or exception text
- this owner has transport authority only
- no payment, deployment, entitlement, package, MT5, persistence,
  or server-side business authority is owned here
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.request import (
    Request,
    urlopen,
)


_ACCESS_CODE_EXCHANGE_PATH = (
    "/customer/setup/access-code/exchange"
)

_DEFAULT_TIMEOUT_SECONDS = 10.0

_GENERIC_TRANSPORT_ERROR = (
    "Customer setup activation exchange failed."
)


def _require_exact_required_string(
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

    if (
        not value
        or value.strip() != value
    ):
        raise ValueError(
            f"{name} must not be empty "
            "and must be normalized."
        )

    return value


def _normalize_setup_base_url(
    value: str,
) -> str:
    normalized = (
        _require_exact_required_string(
            value,
            name="setup_base_url",
        )
    )

    if not (
        normalized.startswith(
            "https://"
        )
        or normalized.startswith(
            "http://"
        )
    ):
        raise ValueError(
            "setup_base_url must use HTTP or HTTPS."
        )

    return normalized.rstrip(
        "/"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class CustomerSetupAccessCodeTransportResult:
    """
    Successful customer-side Activation Code exchange result.

    authorization_code is an internal bootstrap secret and must
    immediately continue into the existing bootstrap acquisition.
    """

    authorization_code: str = field(
        repr=False
    )

    expires_at: str

    def __post_init__(
        self,
    ) -> None:
        _require_exact_required_string(
            self.authorization_code,
            name="authorization_code",
        )

        _require_exact_required_string(
            self.expires_at,
            name="expires_at",
        )


class CustomerSetupAccessCodeHttpClient:
    """
    Minimal transport client for the customer Activation Code exchange.
    """

    __slots__ = (
        "_setup_base_url",
    )

    def __init__(
        self,
        *,
        setup_base_url: str,
    ) -> None:
        self._setup_base_url = (
            _normalize_setup_base_url(
                setup_base_url
            )
        )

    def exchange(
        self,
        *,
        activation_code: str,
        code_challenge_s256: str,
    ) -> CustomerSetupAccessCodeTransportResult:
        normalized_activation_code = (
            _require_exact_required_string(
                activation_code,
                name="activation_code",
            )
        )

        normalized_challenge = (
            _require_exact_required_string(
                code_challenge_s256,
                name="code_challenge_s256",
            )
        )

        payload = json.dumps(
            {
                "activation_code": (
                    normalized_activation_code
                ),
                "code_challenge_s256": (
                    normalized_challenge
                ),
            },
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        )

        request = Request(
            (
                self._setup_base_url
                + _ACCESS_CODE_EXCHANGE_PATH
            ),
            data=payload,
            headers={
                "Content-Type": (
                    "application/json"
                ),
                "Accept": (
                    "application/json"
                ),
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=(
                    _DEFAULT_TIMEOUT_SECONDS
                ),
            ) as response:
                status = getattr(
                    response,
                    "status",
                    None,
                )

                if status != 200:
                    raise RuntimeError(
                        _GENERIC_TRANSPORT_ERROR
                    )

                response_body = (
                    response.read()
                )

        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
        ):
            raise RuntimeError(
                _GENERIC_TRANSPORT_ERROR
            ) from None

        try:
            payload = json.loads(
                response_body.decode(
                    "utf-8"
                )
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            raise RuntimeError(
                "Customer setup activation response "
                "has invalid schema."
            ) from None

        if not isinstance(
            payload,
            dict,
        ):
            raise RuntimeError(
                "Customer setup activation response "
                "has invalid schema."
            )

        if set(
            payload
        ) != {
            "authorization_code",
            "expires_at",
        }:
            raise RuntimeError(
                "Customer setup activation response "
                "has invalid schema."
            )

        try:
            authorization_code = (
                _require_exact_required_string(
                    payload[
                        "authorization_code"
                    ],
                    name=(
                        "authorization_code"
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
                "Customer setup activation response "
                "has invalid schema."
            ) from None

        return (
            CustomerSetupAccessCodeTransportResult(
                authorization_code=(
                    authorization_code
                ),
                expires_at=expires_at,
            )
        )