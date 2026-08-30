"""
TODOBA Customer Setup Bootstrap Input

Immutable in-memory input required to compose the customer
TODOBA Setup application.

This owner validates only:
- the TODOBA Setup service base URL
- the short-lived setup launch credential

It does not acquire, persist, transmit, or interpret either
value.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from urllib.parse import urlsplit


@dataclass(
    frozen=True,
    slots=True,
)
class CustomerSetupBootstrapInput:
    """
    Customer Setup launch input held only in process memory.
    """

    setup_base_url: str
    setup_launch_credential: str = field(
        repr=False
    )

    def __post_init__(
        self,
    ) -> None:
        normalized_url = (
            _normalize_setup_base_url(
                self.setup_base_url
            )
        )

        normalized_credential = (
            _normalize_setup_launch_credential(
                self.setup_launch_credential
            )
        )

        object.__setattr__(
            self,
            "setup_base_url",
            normalized_url,
        )

        object.__setattr__(
            self,
            "setup_launch_credential",
            normalized_credential,
        )


def _normalize_setup_base_url(
    value,
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

    parsed = urlsplit(
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


def _normalize_setup_launch_credential(
    value,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "setup_launch_credential must be str."
        )

    if (
        not value
        or value.strip() != value
    ):
        raise ValueError(
            "setup_launch_credential is invalid."
        )

    return value