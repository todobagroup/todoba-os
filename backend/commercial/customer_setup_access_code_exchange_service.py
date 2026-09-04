"""
TODOBA Customer Setup Access Code Exchange Service.

Commercial Setup boundary:

    customer-facing Activation Code
        + customer-generated PKCE S256 challenge
        -> authoritative Setup access-code authorization
        -> server-derived customer identity
        -> existing bootstrap authorization issuance
        -> short-lived internal authorization code

The returned bootstrap authorization code is an internal
transport secret used immediately by the customer Setup
bootstrap acquisition flow. It is never customer-facing.

Security rules:
- activation_code is the only customer bearer authority
- customer_id is always server-derived
- setup_activation_id is never accepted from the caller
- PKCE challenge is public client binding material, not
  customer authority
- authorization_request_id is server-derived
- no plaintext secret is persisted by this owner
- no payment, subscription, deployment, entitlement, MT5,
  package, HTTP, browser, or production-composition authority
  is owned here
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Callable

from backend.commercial.customer_setup_access_code_service import (
    CustomerSetupAccessCodeAuthorization,
)
from backend.commercial.customer_setup_bootstrap_authorization_service import (
    CustomerSetupBootstrapAuthorizationIssuance,
)


_REQUEST_ID_PREFIX = "setup-access-exchange-"


@dataclass(frozen=True)
class CustomerSetupAccessCodeExchangeResult:
    """
    Minimal secret result consumed internally by Setup.

    Customer and Setup Activation identity deliberately do not
    cross back through this result.
    """

    authorization_code: str = field(
        repr=False
    )
    expires_at: datetime

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.authorization_code,
            str,
        ):
            raise TypeError(
                "authorization_code must be str."
            )

        if (
            not self.authorization_code
            or self.authorization_code.strip()
            != self.authorization_code
        ):
            raise ValueError(
                "authorization_code must be normalized."
            )

        normalized_expiry = (
            self._normalize_aware_datetime(
                self.expires_at,
                name="expires_at",
            )
        )

        object.__setattr__(
            self,
            "expires_at",
            normalized_expiry,
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupAccessCodeExchangeResult("
            "authorization_code=<redacted>, "
            f"expires_at={self.expires_at!r})"
        )

    @staticmethod
    def _normalize_aware_datetime(
        value: datetime,
        *,
        name: str,
    ) -> datetime:
        if not isinstance(
            value,
            datetime,
        ):
            raise TypeError(
                f"{name} must be datetime."
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                f"{name} must be timezone-aware."
            )

        return value.astimezone(
            timezone.utc
        )


class CustomerSetupAccessCodeExchangeService:
    """
    Convert one valid customer Activation Code into one
    PKCE-bound internal bootstrap authorization.

    Dependencies are injected as narrow callables so this owner
    cannot acquire unrelated commercial or persistence authority.
    """

    def __init__(
        self,
        *,
        authorize_access_code: Callable,
        issue_bootstrap_authorization: Callable,
        clock: Callable[[], datetime],
    ) -> None:
        if not callable(
            authorize_access_code
        ):
            raise TypeError(
                "authorize_access_code must be callable."
            )

        if not callable(
            issue_bootstrap_authorization
        ):
            raise TypeError(
                "issue_bootstrap_authorization "
                "must be callable."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self._authorize_access_code = (
            authorize_access_code
        )
        self._issue_bootstrap_authorization = (
            issue_bootstrap_authorization
        )
        self._clock = clock

    def exchange(
        self,
        *,
        activation_code: str,
        code_challenge_s256: str,
    ) -> CustomerSetupAccessCodeExchangeResult:
        """
        Exchange customer-facing authority for an internal
        PKCE-bound bootstrap authorization.

        No caller-supplied customer or Setup Activation identity
        is accepted.
        """

        normalized_activation_code = (
            self._normalize_required_string(
                activation_code,
                name="activation_code",
            )
        )

        normalized_challenge = (
            self._normalize_required_string(
                code_challenge_s256,
                name="code_challenge_s256",
            )
        )

        authorization = (
            self._authorize_access_code(
                activation_code=(
                    normalized_activation_code
                )
            )
        )

        if not isinstance(
            authorization,
            CustomerSetupAccessCodeAuthorization,
        ):
            raise RuntimeError(
                "Access-code authorization returned "
                "an invalid result."
            )

        current_time = (
            self._normalize_trusted_time(
                self._clock()
            )
        )

        authorization_request_id = (
            self._derive_authorization_request_id(
                activation_code=(
                    normalized_activation_code
                ),
                code_challenge_s256=(
                    normalized_challenge
                ),
            )
        )

        issuance = (
            self._issue_bootstrap_authorization(
                authorization_request_id=(
                    authorization_request_id
                ),
                customer_id=(
                    authorization.customer_id
                ),
                code_challenge_s256=(
                    normalized_challenge
                ),
                current_time=current_time,
            )
        )

        if not isinstance(
            issuance,
            CustomerSetupBootstrapAuthorizationIssuance,
        ):
            raise RuntimeError(
                "Bootstrap authorization issuance returned "
                "an invalid result."
            )

        if (
            issuance.customer_id
            != authorization.customer_id
        ):
            raise RuntimeError(
                "Bootstrap authorization customer identity "
                "does not match authoritative access-code "
                "identity."
            )

        if (
            issuance.authorization_request_id
            != authorization_request_id
        ):
            raise RuntimeError(
                "Bootstrap authorization request identity "
                "does not match the server-derived request."
            )

        return CustomerSetupAccessCodeExchangeResult(
            authorization_code=(
                issuance.authorization_code
            ),
            expires_at=(
                issuance.expires_at
            ),
        )

    @staticmethod
    def _derive_authorization_request_id(
        *,
        activation_code: str,
        code_challenge_s256: str,
    ) -> str:
        material = (
            activation_code.encode(
                "utf-8"
            )
            + b"\x00"
            + code_challenge_s256.encode(
                "utf-8"
            )
        )

        digest = hashlib.sha256(
            material
        ).hexdigest()

        return (
            f"{_REQUEST_ID_PREFIX}{digest}"
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
                f"{name} must not be empty."
            )

        if normalized != value:
            raise ValueError(
                f"{name} must be normalized."
            )

        return normalized

    @staticmethod
    def _normalize_trusted_time(
        value: datetime,
    ) -> datetime:
        if not isinstance(
            value,
            datetime,
        ):
            raise TypeError(
                "clock must return datetime."
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "clock must return timezone-aware datetime."
            )

        return value.astimezone(
            timezone.utc
        )