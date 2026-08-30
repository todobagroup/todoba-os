"""
TODOBA Customer Setup Entry HTTP Client

Customer-side transport that exchanges one short-lived setup
launch credential for one short-lived setup handoff credential.

Transport flow:

    setup_base_url
    + setup_launch_credential
        -> POST /customer/setup/entry
        -> Authorization: Bearer <launch credential>
        -> HTTP 200
        -> handoff_credential + expires_at

Safety rules:
- no customer_id is sent
- no deployment_id, agent_id, account, package, or MT5 data
  is sent
- request has no customer-controlled body
- launch credential is never persisted or returned
- launch credential is redacted from repr()
- handoff credential is redacted from result repr()
- response status and schema are fail-closed
- server error bodies are never surfaced through this owner
- this owner does not read environment or runtime config
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import math

import httpx


_ENTRY_PATH = "/customer/setup/entry"


@dataclass(
    frozen=True,
    slots=True,
)
class CustomerSetupEntryTransportResult:
    """
    Successful customer-side setup entry exchange result.

    The plaintext handoff credential must reach the next
    customer Setup transport boundary but must not appear in
    repr().
    """

    handoff_credential: str = field(
        repr=False
    )
    expires_at: str

    def __post_init__(
        self,
    ) -> None:
        _require_exact_required_string(
            self.handoff_credential,
            name="handoff_credential",
        )
        _require_exact_required_string(
            self.expires_at,
            name="expires_at",
        )


class CustomerSetupEntryHttpClient:
    """
    Synchronous customer-side setup-entry exchange transport.
    """

    def __init__(
        self,
        *,
        setup_base_url: str,
        setup_launch_credential: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        normalized_url = _normalize_base_url(
            setup_base_url
        )

        normalized_credential = (
            _require_exact_required_string(
                setup_launch_credential,
                name="setup_launch_credential",
            )
        )

        normalized_timeout = (
            _normalize_timeout_seconds(
                timeout_seconds
            )
        )

        self._setup_base_url = normalized_url
        self._setup_launch_credential = (
            normalized_credential
        )
        self._timeout_seconds = (
            normalized_timeout
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupEntryHttpClient("
            f"setup_base_url="
            f"{self._setup_base_url!r}, "
            "setup_launch_credential=<redacted>, "
            f"timeout_seconds="
            f"{self._timeout_seconds!r})"
        )

    def exchange(
        self,
    ) -> CustomerSetupEntryTransportResult:
        """
        Exchange the launch credential for one setup handoff.

        No request body is sent.
        """

        try:
            response = httpx.post(
                (
                    f"{self._setup_base_url}"
                    f"{_ENTRY_PATH}"
                ),
                headers=self._authentication_headers(),
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError:
            raise RuntimeError(
                "Customer setup entry request failed."
            ) from None

        if response.status_code != 200:
            raise RuntimeError(
                "Customer setup entry request was rejected."
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
                "Customer setup entry response has "
                "invalid content type."
            )

        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError(
                "Customer setup entry response is not "
                "valid JSON."
            ) from None

        if not isinstance(
            payload,
            dict,
        ):
            raise RuntimeError(
                "Customer setup entry response has "
                "invalid schema."
            )

        if set(
            payload
        ) != {
            "handoff_credential",
            "expires_at",
        }:
            raise RuntimeError(
                "Customer setup entry response has "
                "invalid schema."
            )

        try:
            handoff_credential = (
                _require_exact_required_string(
                    payload[
                        "handoff_credential"
                    ],
                    name="handoff_credential",
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
                "Customer setup entry response has "
                "invalid schema."
            ) from None

        return CustomerSetupEntryTransportResult(
            handoff_credential=(
                handoff_credential
            ),
            expires_at=expires_at,
        )

    def _authentication_headers(
        self,
    ) -> dict[str, str]:
        return {
            "Authorization": (
                "Bearer "
                f"{self._setup_launch_credential}"
            ),
            "Accept": "application/json",
        }


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