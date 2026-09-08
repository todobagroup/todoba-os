"""
TODOBA VPS Connect Grant HTTP Client.

Customer-safe transport for obtaining one short-lived
VPS Connect grant from TODOBA Cloud.

Public caller supplies only:
- activation_code
- account_fingerprint

Public result exposes only:
- grant_credential
- expires_at

This owner has no persistence, deployment, provisioning,
MT5, VPS, or backend composition authority.
"""

from dataclasses import dataclass, field
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


_VPS_CONNECT_GRANT_PATH = (
    "/customer/vps-connect/grant"
)

_VPS_CONNECT_USER_AGENT = (
    "TODOBA-VPS-Connect/1.0"
)

_DEFAULT_TIMEOUT_SECONDS = 5.0


def _normalize_required_string(
    value: str,
    *,
    name: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{name} must be str."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{name} is required."
        )

    return normalized


def _normalize_cloud_base_url(
    value: str,
) -> str:
    normalized = _normalize_required_string(
        value,
        name="cloud_base_url",
    ).rstrip("/")

    parsed = urlsplit(
        normalized
    )

    if parsed.scheme not in {
        "http",
        "https",
    }:
        raise ValueError(
            "cloud_base_url must use HTTP or HTTPS."
        )

    if not parsed.hostname:
        raise ValueError(
            "cloud_base_url must contain a host."
        )

    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(
            "cloud_base_url must not contain user info."
        )

    if parsed.query:
        raise ValueError(
            "cloud_base_url must not contain query."
        )

    if parsed.fragment:
        raise ValueError(
            "cloud_base_url must not contain fragment."
        )

    if parsed.path not in {
        "",
        "/",
    }:
        raise ValueError(
            "cloud_base_url must not contain a path."
        )

    return normalized


@dataclass(
    frozen=True,
)
class CustomerVPSConnectGrantTransportResult:
    grant_credential: str = field(
        repr=False,
    )
    expires_at: str

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "grant_credential",
            _normalize_required_string(
                self.grant_credential,
                name="grant_credential",
            ),
        )

        object.__setattr__(
            self,
            "expires_at",
            _normalize_required_string(
                self.expires_at,
                name="expires_at",
            ),
        )


class CustomerVPSConnectGrantHttpClient:
    """
    Minimal customer-side VPS Connect grant transport.
    """

    def __init__(
        self,
        *,
        cloud_base_url: str,
        timeout_seconds: float = (
            _DEFAULT_TIMEOUT_SECONDS
        ),
    ) -> None:
        normalized_url = (
            _normalize_cloud_base_url(
                cloud_base_url
            )
        )

        if not isinstance(
            timeout_seconds,
            (int, float),
        ):
            raise TypeError(
                "timeout_seconds must be numeric."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        self._cloud_base_url = (
            normalized_url
        )
        self._timeout_seconds = float(
            timeout_seconds
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerVPSConnectGrantHttpClient("
            f"cloud_base_url="
            f"{self._cloud_base_url!r}, "
            f"timeout_seconds="
            f"{self._timeout_seconds!r})"
        )

    def issue(
        self,
        *,
        activation_code: str,
        account_fingerprint: str,
    ) -> CustomerVPSConnectGrantTransportResult:
        normalized_activation_code = (
            _normalize_required_string(
                activation_code,
                name="activation_code",
            )
        )

        normalized_account_fingerprint = (
            _normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        request_payload = {
            "activation_code": (
                normalized_activation_code
            ),
            "account_fingerprint": (
                normalized_account_fingerprint
            ),
        }

        request = Request(
            (
                self._cloud_base_url
                + _VPS_CONNECT_GRANT_PATH
            ),
            data=json.dumps(
                request_payload,
                separators=(",", ":"),
            ).encode(
                "utf-8"
            ),
            headers={
                "Content-Type": (
                    "application/json"
                ),
                "Accept": (
                    "application/json"
                ),
                "User-Agent": (
                    _VPS_CONNECT_USER_AGENT
                ),
            },
            method="POST",
        )

        # Keep urlopen exposed at module scope so transport
        # tests can replace it without network access.
        # Invoke through an alias so this owner does not
        # resemble or acquire filesystem open authority.
        transport = urlopen

        try:
            with transport(
                request,
                timeout=(
                    self._timeout_seconds
                ),
            ) as response:
                status = getattr(
                    response,
                    "status",
                    None,
                )

                if status != 200:
                    raise RuntimeError(
                        "TODOBA VPS Connect grant "
                        "request failed."
                    )

                raw_body = response.read()

        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
        ) as exc:
            raise RuntimeError(
                "TODOBA VPS Connect grant "
                "request failed."
            ) from exc

        try:
            payload: Any = json.loads(
                raw_body.decode(
                    "utf-8"
                )
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(
                "Invalid TODOBA VPS Connect "
                "grant response."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise RuntimeError(
                "Invalid TODOBA VPS Connect "
                "grant response."
            )

        if set(payload) != {
            "grant_credential",
            "expires_at",
        }:
            raise RuntimeError(
                "Invalid TODOBA VPS Connect "
                "grant response shape."
            )

        try:
            return (
                CustomerVPSConnectGrantTransportResult(
                    grant_credential=(
                        payload[
                            "grant_credential"
                        ]
                    ),
                    expires_at=(
                        payload[
                            "expires_at"
                        ]
                    ),
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "Invalid TODOBA VPS Connect "
                "grant response."
            ) from exc
