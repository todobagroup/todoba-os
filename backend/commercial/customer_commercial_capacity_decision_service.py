from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from backend.commercial.customer_commercial_billing_cycle_baseline_service import (
    CustomerCommercialBillingCycleBaselineRecord,
)
from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBinding,
)
from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlement,
    CustomerCommercialEntitlementStatus,
)
from backend.commercial.customer_commercial_external_funding_observation_service import (
    CustomerCommercialExternalFundingObservationRecord,
)


_OPERATIONAL_GRACE_MULTIPLIER = Decimal("1.05")


class CustomerCommercialCapacityDecisionStatus(str, Enum):
    ALLOW_NEW_EXPOSURE = "ALLOW_NEW_EXPOSURE"
    UPGRADE_REQUIRED = "UPGRADE_REQUIRED"


@dataclass(frozen=True)
class CustomerCommercialCapacityDecision:
    commercial_entitlement_id: str
    deployment_id: str
    cycle_id: str
    licensed_account_cap_usd: Decimal
    operational_grace_limit_usd: Decimal
    commercial_capacity_high_water_usd: Decimal
    status: CustomerCommercialCapacityDecisionStatus


class CustomerCommercialCapacityDecisionService:
    """
    Decide in-cycle commercial capacity from authoritative facts only.
    """

    def decide(
        self,
        *,
        entitlement: CustomerCommercialEntitlement,
        deployment_binding: CustomerCommercialDeploymentBinding,
        billing_cycle_baseline: CustomerCommercialBillingCycleBaselineRecord,
        external_funding_observations: tuple[
            CustomerCommercialExternalFundingObservationRecord,
            ...,
        ],
    ) -> CustomerCommercialCapacityDecision:
        if not isinstance(
            entitlement,
            CustomerCommercialEntitlement,
        ):
            raise TypeError(
                "entitlement must be CustomerCommercialEntitlement."
            )

        if not isinstance(
            deployment_binding,
            CustomerCommercialDeploymentBinding,
        ):
            raise TypeError(
                "deployment_binding must be "
                "CustomerCommercialDeploymentBinding."
            )

        if not isinstance(
            billing_cycle_baseline,
            CustomerCommercialBillingCycleBaselineRecord,
        ):
            raise TypeError(
                "billing_cycle_baseline must be "
                "CustomerCommercialBillingCycleBaselineRecord."
            )

        if not isinstance(
            external_funding_observations,
            tuple,
        ):
            raise TypeError(
                "external_funding_observations must be tuple."
            )

        if (
            entitlement.status
            is not CustomerCommercialEntitlementStatus.ACTIVE
        ):
            raise ValueError(
                "Capacity decision requires an "
                "ACTIVE commercial entitlement."
            )

        if (
            deployment_binding.commercial_entitlement_id
            != entitlement.entitlement_id
        ):
            raise ValueError(
                "Commercial entitlement identity does not match "
                "deployment binding."
            )

        if (
            deployment_binding.customer_id
            != entitlement.customer_id
        ):
            raise ValueError(
                "Commercial customer identity does not match "
                "deployment binding."
            )

        if (
            billing_cycle_baseline.customer_id
            != entitlement.customer_id
        ):
            raise ValueError(
                "Commercial customer identity does not match "
                "billing cycle baseline."
            )

        if (
            billing_cycle_baseline.licensed_account_cap_usd
            != entitlement.licensed_account_cap_usd
        ):
            raise ValueError(
                "Billing cycle licensed account cap does not match "
                "purchased entitlement."
            )

        licensed_cap = Decimal(
            entitlement.licensed_account_cap_usd
        )

        operational_grace_limit = (
            licensed_cap
            * _OPERATIONAL_GRACE_MULTIPLIER
        )

        commercial_capacity_high_water = (
            billing_cycle_baseline.authoritative_cycle_balance_usd
        )

        replay_identities: set[
            tuple[str, int]
        ] = set()

        for observation in external_funding_observations:
            if not isinstance(
                observation,
                CustomerCommercialExternalFundingObservationRecord,
            ):
                raise TypeError(
                    "external_funding_observations must contain "
                    "CustomerCommercialExternalFundingObservationRecord."
                )

            if (
                observation.cycle_id
                != billing_cycle_baseline.cycle_id
            ):
                raise ValueError(
                    "External funding observation does not belong "
                    "to the authoritative billing cycle."
                )

            if (
                observation.account_fingerprint
                != deployment_binding.account_fingerprint
            ):
                raise ValueError(
                    "External funding observation account fingerprint "
                    "does not match bound account."
                )

            replay_identity = (
                observation.account_fingerprint,
                observation.deal_ticket,
            )

            if replay_identity in replay_identities:
                raise ValueError(
                    "Duplicate external funding replay identity."
                )

            replay_identities.add(
                replay_identity
            )

            if observation.funding_kind == "external_deposit":
                commercial_capacity_high_water += observation.amount
            elif observation.funding_kind == "external_withdrawal":
                continue
            else:
                raise ValueError(
                    "External funding observation kind is unsupported."
                )

        if (
            commercial_capacity_high_water
            > operational_grace_limit
        ):
            status = (
                CustomerCommercialCapacityDecisionStatus
                .UPGRADE_REQUIRED
            )
        else:
            status = (
                CustomerCommercialCapacityDecisionStatus
                .ALLOW_NEW_EXPOSURE
            )

        return CustomerCommercialCapacityDecision(
            commercial_entitlement_id=(
                entitlement.entitlement_id
            ),
            deployment_id=(
                deployment_binding.deployment_id
            ),
            cycle_id=(
                billing_cycle_baseline.cycle_id
            ),
            licensed_account_cap_usd=licensed_cap,
            operational_grace_limit_usd=(
                operational_grace_limit
            ),
            commercial_capacity_high_water_usd=(
                commercial_capacity_high_water
            ),
            status=status,
        )
