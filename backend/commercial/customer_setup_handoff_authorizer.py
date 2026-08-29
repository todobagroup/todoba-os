"""
TODOBA Customer Setup Handoff Authorizer

Production authorization adapter between customer setup HTTP
boundaries and the authoritative R3 handoff service.

Ownership:
- obtain the current time from one injectable clock
- require a timezone-aware datetime
- normalize the clock value to UTC
- delegate credential authorization to
  CustomerSetupHandoffService

This component does not:
- issue handoff credentials
- revoke handoff credentials
- initialize durable state
- mutate activation or handoff state directly
- own HTTP or FastAPI behavior
- own package, deployment, entitlement, or bootstrap state
- import backend.main
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from datetime import timezone

from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffAuthorization,
    CustomerSetupHandoffService,
)


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


class CustomerSetupHandoffAuthorizer:
    """
    Bind R3 handoff authorization to one trusted UTC clock.
    """

    def __init__(
        self,
        *,
        handoff_service: CustomerSetupHandoffService,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not isinstance(
            handoff_service,
            CustomerSetupHandoffService,
        ):
            raise TypeError(
                "handoff_service must be "
                "CustomerSetupHandoffService."
            )

        if not callable(
            clock
        ):
            raise TypeError(
                "clock must be callable."
            )

        self._handoff_service = handoff_service
        self._clock = clock

    def authorize(
        self,
        handoff_credential: str,
    ) -> CustomerSetupHandoffAuthorization:
        current_time = self._clock()

        if not isinstance(
            current_time,
            datetime,
        ):
            raise TypeError(
                "clock must return datetime."
            )

        if (
            current_time.tzinfo is None
            or current_time.utcoffset() is None
        ):
            raise ValueError(
                "clock must return timezone-aware datetime."
            )

        current_time_utc = (
            current_time.astimezone(
                timezone.utc
            )
        )

        return self._handoff_service.authorize(
            handoff_credential=handoff_credential,
            current_time=current_time_utc,
        )
