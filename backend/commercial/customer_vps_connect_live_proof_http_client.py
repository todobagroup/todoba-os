"""
TODOBA VPS Connect Live Proof HTTP Client.

Customer-side transport for server-backed VPS live proof.

Input:
- one in-memory VPS Connect grant credential

Public result:
- VPS proof status only

This owner has no persistence, deployment mutation,
MT5 operation, VPS operation, or backend composition authority.
"""

from dataclasses import dataclass
import json
from typing import Any
from typing import Literal
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request
from urllib.request import urlopen


_VPS_CONNECT_LIVE_PROOF_PATH = (
    "/customer/vps-connect/live-proof"
)

_VPS_CONNECT_USER_AGENT = (
    "TODOBA-VPS-Connect/1.0"
)

_DEFAULT_TIMEOUT_SECONDS = 5.0

_ALLOWED_STATUSES = frozenset(
    {
        "vps_pending",
        "vps_online",
    }
)

_GENERIC_TRANSPORT_ERROR = (
    "TODOBA VPS Connect live proof request failed."
)

_GENERIC_RESPONSE_ERROR = (
    "Invalid TODOBA VPS Connect live proof response."
)


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


def _normalize_cloud_base_url(
    value: str,
) -> str:
    normalized = _normalize_required_string(
        value,
        name="cloud_base_url",
    )

    parsed = urlsplit(
        normalized
    )

    if parsed.scheme not in (
        "http",
        "https",
    ):
        raise ValueError(
            "cloud_base_url must use http or https."
        )

    if not parsed.hostname:
        raise ValueError(
            "cloud_base_url host is required."
        )

    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(
            "cloud_base_url user information is forbidden."
        )

    if parsed.path not in (
        "",
        "/",
    ):
        raise ValueError(
            "cloud_base_url path is forbidden."
        )

    if parsed.query:
        raise ValueError(
            "cloud_base_url query is forbidden."
        )

    if parsed.fragment:
        raise ValueError(
            "cloud_base_url fragment is forbidden."
        )

    return normalized.rstrip(
        "/"
    )


@dataclass(
    frozen=True,
)
class CustomerVPSConnectLiveProofTransportResult:
    status: Literal[
        "vps_pending",
        "vps_online",
    ]

    def __post_init__(
        self,
    ) -> None:
        normalized_status = (
            _normalize_required_string(
                self.status,
                name="status",
            )
        )

        if normalized_status not in (
            _ALLOWED_STATUSES
        ):
            raise ValueError(
                "Unsupported VPS Connect "
                "live proof status."
            )

        object.__setattr__(
            self,
            "status",
            normalized_status,
        )


class CustomerVPSConnectLiveProofHttpClient:
    """
    Minimal customer-side live-proof HTTP transport.
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
        ) or isinstance(
            timeout_seconds,
            bool,
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
            "CustomerVPSConnectLiveProofHttpClient("
            f"cloud_base_url="
            f"{self._cloud_base_url!r}, "
            f"timeout_seconds="
            f"{self._timeout_seconds!r})"
        )

    def verify(
        self,
        *,
        grant_credential: str,
    ) -> CustomerVPSConnectLiveProofTransportResult:
        normalized_grant = (
            _normalize_required_string(
                grant_credential,
                name="grant_credential",
            )
        )

        body = json.dumps(
            {
                "grant_credential": (
                    normalized_grant
                ),
            }
        ).encode(
            "utf-8"
        )

        request = Request(
            (
                self._cloud_base_url
                + _VPS_CONNECT_LIVE_PROOF_PATH
            ),
            data=body,
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

        transport = urlopen

        try:
            with transport(
                request,
                timeout=(
                    self._timeout_seconds
                ),
            ) as response:
                status_code = getattr(
                    response,
                    "status",
                    None,
                )

                if status_code != 200:
                    raise RuntimeError(
                        _GENERIC_TRANSPORT_ERROR
                    )

                raw_body = response.read()

        except RuntimeError:
            raise
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
        ) as exc:
            raise RuntimeError(
                _GENERIC_TRANSPORT_ERROR
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
            AttributeError,
        ) as exc:
            raise RuntimeError(
                _GENERIC_RESPONSE_ERROR
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise RuntimeError(
                _GENERIC_RESPONSE_ERROR
            )

        if set(payload) != {
            "status",
        }:
            raise RuntimeError(
                _GENERIC_RESPONSE_ERROR
            )

        try:
            return (
                CustomerVPSConnectLiveProofTransportResult(
                    status=payload[
                        "status"
                    ],
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                _GENERIC_RESPONSE_ERROR
            ) from exc