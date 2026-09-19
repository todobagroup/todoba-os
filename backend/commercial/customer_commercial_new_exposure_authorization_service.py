from __future__ import annotations

from backend.commercial.customer_commercial_capacity_decision_service import (
    CustomerCommercialCapacityDecision,
    CustomerCommercialCapacityDecisionStatus,
)


class CustomerCommercialNewExposureAuthorizationService:
    """
    Authorize creation of new exposure from a commercial
    capacity decision only.
    """

    def authorize(
        self,
        *,
        capacity_decision: CustomerCommercialCapacityDecision,
    ) -> None:
        if not isinstance(
            capacity_decision,
            CustomerCommercialCapacityDecision,
        ):
            raise TypeError(
                "capacity_decision must be "
                "CustomerCommercialCapacityDecision."
            )

        if (
            capacity_decision.status
            is CustomerCommercialCapacityDecisionStatus
            .ALLOW_NEW_EXPOSURE
        ):
            return None

        if (
            capacity_decision.status
            is CustomerCommercialCapacityDecisionStatus
            .UPGRADE_REQUIRED
        ):
            raise RuntimeError(
                "Commercial upgrade required before new exposure."
            )

        raise RuntimeError(
            "Commercial capacity decision status is not authorized."
        )
