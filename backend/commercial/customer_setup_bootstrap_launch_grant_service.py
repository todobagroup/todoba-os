"""
TODOBA Customer Setup Bootstrap Launch Grant Service

Trusted application orchestration between one-time PKCE bootstrap
authorization and the existing short-lived customer setup launch
credential owner.

Trust flow:

    authorization_code
    code_verifier
    current_time
        -> bootstrap authorization redeem
        -> consumed-redemption recovery on retry only
        -> authoritative customer identity
        -> deterministic launch issuance request identity
        -> CustomerSetupLaunchCredentialService.issue()
        -> short-lived setup launch credential

Ownership rules:
- caller never supplies customer_id
- bootstrap authorization remains authoritative for customer identity
- launch credential issuance remains owned by the existing launch
  credential service
- this owner creates no durable state
- plaintext authorization code and PKCE verifier are never persisted
  here
- plaintext setup launch credential is returned only in the grant
  result and is redacted from repr()
- retry after a consumed authorization is allowed only through the
  bootstrap authorization owner's dedicated recovery contract
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from hashlib import sha256
import threading

from backend.commercial.customer_setup_bootstrap_authorization_service import (
    CustomerSetupBootstrapAuthorizationRedemption,
)
from backend.commercial.customer_setup_launch_credential_service import (
    CustomerSetupLaunchCredentialIssuanceResult,
)


_LAUNCH_ISSUANCE_REQUEST_PREFIX = (
    "bootstrap-launch-"
)


@dataclass(
    frozen=True,
    repr=False,
    slots=True,
)
class CustomerSetupBootstrapLaunchGrantResult:
    """
    Safe result of one trusted bootstrap-to-launch grant.
    """

    authorization_id: str
    customer_id: str
    consumed_at: str
    launch_issuance_request_id: str
    launch_id: str
    issued_at: str
    expires_at: str
    setup_launch_credential: str = field(
        repr=False,
    )

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "authorization_id",
            "customer_id",
            "consumed_at",
            "launch_issuance_request_id",
            "launch_id",
            "issued_at",
            "expires_at",
            "setup_launch_credential",
        ):
            object.__setattr__(
                self,
                name,
                _normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupBootstrapLaunchGrantResult("
            f"authorization_id="
            f"{self.authorization_id!r}, "
            f"customer_id={self.customer_id!r}, "
            f"consumed_at={self.consumed_at!r}, "
            f"launch_issuance_request_id="
            f"{self.launch_issuance_request_id!r}, "
            f"launch_id={self.launch_id!r}, "
            f"issued_at={self.issued_at!r}, "
            f"expires_at={self.expires_at!r}, "
            "setup_launch_credential=<redacted>)"
        )


def derive_customer_setup_bootstrap_launch_issuance_request_id(
    authorization_id: str,
) -> str:
    """
    Derive the stable launch issuance identity for one bootstrap
    authorization without persisting the authorization id itself as
    the downstream request id.
    """

    normalized_authorization_id = (
        _normalize_required_string(
            authorization_id,
            name="authorization_id",
        )
    )

    digest = sha256(
        normalized_authorization_id.encode(
            "utf-8"
        )
    ).hexdigest()

    return (
        f"{_LAUNCH_ISSUANCE_REQUEST_PREFIX}"
        f"{digest}"
    )


class CustomerSetupBootstrapLaunchGrantService:
    """
    Exchange trusted PKCE bootstrap authority for one setup launch
    credential without duplicating authoritative durable state.
    """

    def __init__(
        self,
        *,
        bootstrap_authorization_service,
        launch_credential_service,
    ) -> None:
        _require_owner_method(
            bootstrap_authorization_service,
            owner_name=(
                "bootstrap_authorization_service"
            ),
            method_name="redeem",
        )
        _require_owner_method(
            bootstrap_authorization_service,
            owner_name=(
                "bootstrap_authorization_service"
            ),
            method_name=(
                "recover_consumed_redemption"
            ),
        )
        _require_owner_method(
            launch_credential_service,
            owner_name=(
                "launch_credential_service"
            ),
            method_name="issue",
        )

        self._bootstrap_authorization_service = (
            bootstrap_authorization_service
        )
        self._launch_credential_service = (
            launch_credential_service
        )
        self._lock = threading.RLock()

    def grant(
        self,
        *,
        authorization_code: str,
        code_verifier: str,
        current_time: datetime,
    ) -> CustomerSetupBootstrapLaunchGrantResult:
        """
        Redeem or safely recover bootstrap authority and issue the
        corresponding setup launch credential.

        Crash/retry contract:

        1. A first successful bootstrap redemption consumes the
           authorization durably.
        2. If downstream launch issuance or process completion fails,
           the caller may retry the same authorization code and PKCE
           verifier.
        3. The bootstrap authorization owner alone decides whether
           consumed redemption recovery is permitted.
        4. The same authorization_id always derives the same launch
           issuance_request_id.
        5. Existing launch issuance retry semantics remain owned by
           CustomerSetupLaunchCredentialService.
        """

        normalized_current_time = (
            _normalize_datetime(
                current_time
            )
        )

        with self._lock:
            redemption = (
                self._redeem_or_recover(
                    authorization_code=(
                        authorization_code
                    ),
                    code_verifier=(
                        code_verifier
                    ),
                    current_time=(
                        normalized_current_time
                    ),
                )
            )

            if not isinstance(
                redemption,
                CustomerSetupBootstrapAuthorizationRedemption,
            ):
                raise RuntimeError(
                    "Bootstrap authorization owner returned "
                    "invalid redemption."
                )

            launch_issuance_request_id = (
                derive_customer_setup_bootstrap_launch_issuance_request_id(
                    redemption.authorization_id
                )
            )

            issuance = (
                self._launch_credential_service.issue(
                    issuance_request_id=(
                        launch_issuance_request_id
                    ),
                    customer_id=(
                        redemption.customer_id
                    ),
                    current_time=(
                        normalized_current_time
                    ),
                )
            )

            if not isinstance(
                issuance,
                CustomerSetupLaunchCredentialIssuanceResult,
            ):
                raise RuntimeError(
                    "Launch credential owner returned "
                    "invalid issuance result."
                )

            if (
                issuance.issuance_request_id
                != launch_issuance_request_id
            ):
                raise RuntimeError(
                    "Launch credential issuance request "
                    "identity did not converge."
                )

            if (
                issuance.customer_id
                != redemption.customer_id
            ):
                raise RuntimeError(
                    "Bootstrap and launch customer "
                    "identity did not converge."
                )

            return (
                CustomerSetupBootstrapLaunchGrantResult(
                    authorization_id=(
                        redemption.authorization_id
                    ),
                    customer_id=(
                        redemption.customer_id
                    ),
                    consumed_at=(
                        redemption.consumed_at
                    ),
                    launch_issuance_request_id=(
                        launch_issuance_request_id
                    ),
                    launch_id=(
                        issuance.launch_id
                    ),
                    issued_at=(
                        issuance.issued_at
                    ),
                    expires_at=(
                        issuance.expires_at
                    ),
                    setup_launch_credential=(
                        issuance.launch_credential
                    ),
                )
            )

    def _redeem_or_recover(
        self,
        *,
        authorization_code: str,
        code_verifier: str,
        current_time: datetime,
    ) -> CustomerSetupBootstrapAuthorizationRedemption:
        try:
            return (
                self._bootstrap_authorization_service
                .redeem(
                    authorization_code=(
                        authorization_code
                    ),
                    code_verifier=(
                        code_verifier
                    ),
                    current_time=(
                        current_time
                    ),
                )
            )
        except ValueError as redeem_error:
            try:
                return (
                    self._bootstrap_authorization_service
                    .recover_consumed_redemption(
                        authorization_code=(
                            authorization_code
                        ),
                        code_verifier=(
                            code_verifier
                        ),
                        current_time=(
                            current_time
                        ),
                    )
                )
            except ValueError as recovery_error:
                raise redeem_error from recovery_error


def _normalize_required_string(
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

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{name} is required."
        )

    return normalized


def _normalize_datetime(
    value,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "current_time must be datetime."
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            "current_time must be timezone-aware."
        )

    return value.astimezone(
        timezone.utc
    )


def _require_owner_method(
    owner,
    *,
    owner_name: str,
    method_name: str,
) -> None:
    method = getattr(
        owner,
        method_name,
        None,
    )

    if not callable(
        method
    ):
        raise TypeError(
            f"{owner_name} must expose callable "
            f"{method_name}()."
        )