"""
TODOBA Customer Setup Entry Grant Service

Trusted internal commercial setup-entry orchestration.

Trust flow:

    grant_request_id
    customer_id
    current_time
        -> authoritative customer registration lookup
        -> CustomerSetupActivationService.activate()
        -> CustomerSetupHandoffService.issue()
        -> short-lived setup handoff credential

Ownership rules:
- the customer must already have authoritative registration
- registration truth is read only; this owner never registers customers
- setup activation remains owned by CustomerSetupActivationService
- handoff issuance remains owned by CustomerSetupHandoffService
- this owner creates no duplicate durable state
- one grant_request_id is reused as the downstream activation and
  issuance request identity for deterministic crash recovery
- plaintext handoff credential is returned only in the grant result
  and is redacted from repr()

This component does not expose HTTP or own external authorization
transport. Its caller must already be a trusted commercial authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
import threading

from backend.commercial.customer_registration_service import (
    CustomerRegistrationRecord,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationResult,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffIssuanceResult,
)


@dataclass(
    frozen=True,
    repr=False,
)
class CustomerSetupEntryGrantResult:
    """
    Safe result for one trusted setup-entry grant.

    handoff_credential is intentionally excluded from repr().
    """

    grant_request_id: str
    registration_request_id: str
    customer_id: str
    setup_activation_id: str
    handoff_id: str
    issued_at: str
    expires_at: str
    handoff_credential: str = field(
        repr=False,
    )

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "grant_request_id",
            "registration_request_id",
            "customer_id",
            "setup_activation_id",
            "handoff_id",
            "issued_at",
            "expires_at",
            "handoff_credential",
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
            "CustomerSetupEntryGrantResult("
            f"grant_request_id="
            f"{self.grant_request_id!r}, "
            f"registration_request_id="
            f"{self.registration_request_id!r}, "
            f"customer_id={self.customer_id!r}, "
            f"setup_activation_id="
            f"{self.setup_activation_id!r}, "
            f"handoff_id={self.handoff_id!r}, "
            f"issued_at={self.issued_at!r}, "
            f"expires_at={self.expires_at!r}, "
            "handoff_credential=<redacted>)"
        )


class CustomerSetupEntryGrantService:
    """
    Grant one trusted commercial setup entry without duplicating
    authoritative registration, activation, or handoff state.
    """

    def __init__(
        self,
        *,
        registration_store,
        setup_activation_service,
        handoff_service,
    ) -> None:
        _require_owner_method(
            registration_store,
            owner_name="registration_store",
            method_name="get_by_customer_id",
        )
        _require_owner_method(
            setup_activation_service,
            owner_name="setup_activation_service",
            method_name="activate",
        )
        _require_owner_method(
            handoff_service,
            owner_name="handoff_service",
            method_name="issue",
        )

        self._registration_store = (
            registration_store
        )
        self._setup_activation_service = (
            setup_activation_service
        )
        self._handoff_service = (
            handoff_service
        )
        self._lock = threading.RLock()

    def grant(
        self,
        *,
        grant_request_id: str,
        customer_id: str,
        current_time: datetime,
    ) -> CustomerSetupEntryGrantResult:
        """
        Grant or recover one setup entry.

        Retry contract:
        - same grant request and customer converges on the same
          setup activation identity
        - handoff retry semantics remain authoritative in the
          handoff service
        - crash after activation but before handoff issuance is
          recovered by retrying the same grant_request_id
        """

        normalized_request_id = (
            _normalize_required_string(
                grant_request_id,
                name="grant_request_id",
            )
        )
        normalized_customer_id = (
            _normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        if not isinstance(
            current_time,
            datetime,
        ):
            raise TypeError(
                "current_time must be datetime."
            )

        with self._lock:
            registration = (
                self._registration_store
                .get_by_customer_id(
                    customer_id=(
                        normalized_customer_id
                    )
                )
            )

            if registration is None:
                raise ValueError(
                    "Customer is not authoritatively "
                    "registered."
                )

            if not isinstance(
                registration,
                CustomerRegistrationRecord,
            ):
                raise RuntimeError(
                    "Customer registration store returned "
                    "invalid record."
                )

            if (
                registration.customer_id
                != normalized_customer_id
            ):
                raise RuntimeError(
                    "Customer registration identity "
                    "mismatch."
                )

            activation = (
                self._setup_activation_service.activate(
                    activation_request_id=(
                        normalized_request_id
                    ),
                    customer_id=(
                        normalized_customer_id
                    ),
                )
            )

            if not isinstance(
                activation,
                CustomerSetupActivationResult,
            ):
                raise RuntimeError(
                    "Customer setup activation service "
                    "returned invalid result."
                )

            if (
                activation.activation_request_id
                != normalized_request_id
            ):
                raise RuntimeError(
                    "Setup activation request identity "
                    "did not converge."
                )

            if (
                activation.customer_id
                != normalized_customer_id
            ):
                raise RuntimeError(
                    "Setup activation customer identity "
                    "mismatch."
                )

            handoff = (
                self._handoff_service.issue(
                    issuance_request_id=(
                        normalized_request_id
                    ),
                    setup_activation_id=(
                        activation.setup_activation_id
                    ),
                    current_time=current_time,
                )
            )

            if not isinstance(
                handoff,
                CustomerSetupHandoffIssuanceResult,
            ):
                raise RuntimeError(
                    "Customer setup handoff service "
                    "returned invalid result."
                )

            if (
                handoff.issuance_request_id
                != normalized_request_id
            ):
                raise RuntimeError(
                    "Setup handoff request identity "
                    "did not converge."
                )

            if (
                handoff.setup_activation_id
                != activation.setup_activation_id
            ):
                raise RuntimeError(
                    "Setup handoff activation identity "
                    "mismatch."
                )

            return CustomerSetupEntryGrantResult(
                grant_request_id=(
                    normalized_request_id
                ),
                registration_request_id=(
                    registration.registration_request_id
                ),
                customer_id=(
                    normalized_customer_id
                ),
                setup_activation_id=(
                    activation.setup_activation_id
                ),
                handoff_id=(
                    handoff.handoff_id
                ),
                issued_at=(
                    handoff.issued_at
                ),
                expires_at=(
                    handoff.expires_at
                ),
                handoff_credential=(
                    handoff.handoff_credential
                ),
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
