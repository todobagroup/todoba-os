from __future__ import annotations

from backend.commercial.customer_commercial_capacity_decision_service import (
    CustomerCommercialCapacityDecision,
    CustomerCommercialCapacityDecisionService,
)
from backend.commercial.customer_commercial_current_billing_cycle_service import (
    CustomerCommercialCurrentBillingCycleService,
)
from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBindingStore,
)
from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlementRegistry,
)
from backend.commercial.customer_commercial_external_funding_observation_service import (
    CustomerCommercialExternalFundingObservationStore,
)


class CustomerCommercialCapacityDecisionProvider:
    """
    Resolve fresh authoritative commercial facts for one
    deployment and produce a capacity decision.

    Caller authority is intentionally limited to deployment_id.
    """

    def __init__(
        self,
        *,
        entitlement_registry: CustomerCommercialEntitlementRegistry,
        deployment_binding_store: CustomerCommercialDeploymentBindingStore,
        current_billing_cycle_service: CustomerCommercialCurrentBillingCycleService,
        external_funding_store: CustomerCommercialExternalFundingObservationStore,
        capacity_decision_service: CustomerCommercialCapacityDecisionService,
    ) -> None:
        if not isinstance(
            entitlement_registry,
            CustomerCommercialEntitlementRegistry,
        ):
            raise TypeError(
                "entitlement_registry must be "
                "CustomerCommercialEntitlementRegistry."
            )

        if not isinstance(
            deployment_binding_store,
            CustomerCommercialDeploymentBindingStore,
        ):
            raise TypeError(
                "deployment_binding_store must be "
                "CustomerCommercialDeploymentBindingStore."
            )

        if not isinstance(
            current_billing_cycle_service,
            CustomerCommercialCurrentBillingCycleService,
        ):
            raise TypeError(
                "current_billing_cycle_service must be "
                "CustomerCommercialCurrentBillingCycleService."
            )

        if not isinstance(
            external_funding_store,
            CustomerCommercialExternalFundingObservationStore,
        ):
            raise TypeError(
                "external_funding_store must be "
                "CustomerCommercialExternalFundingObservationStore."
            )

        if not isinstance(
            capacity_decision_service,
            CustomerCommercialCapacityDecisionService,
        ):
            raise TypeError(
                "capacity_decision_service must be "
                "CustomerCommercialCapacityDecisionService."
            )

        if not entitlement_registry.is_ready():
            raise RuntimeError(
                "Commercial entitlement registry is not initialized."
            )

        if not deployment_binding_store.is_ready():
            raise RuntimeError(
                "Commercial deployment binding store is not initialized."
            )

        if not external_funding_store.is_ready():
            raise RuntimeError(
                "External funding observation store is not initialized."
            )

        self._entitlement_registry = entitlement_registry
        self._deployment_binding_store = deployment_binding_store
        self._current_billing_cycle_service = (
            current_billing_cycle_service
        )
        self._external_funding_store = external_funding_store
        self._capacity_decision_service = capacity_decision_service

    def provide(
        self,
        *,
        deployment_id: str,
    ) -> CustomerCommercialCapacityDecision:
        binding = (
            self._deployment_binding_store.get_by_deployment_id(
                deployment_id=deployment_id
            )
        )

        if binding is None:
            raise RuntimeError(
                "Unknown commercial deployment."
            )

        entitlement = self._entitlement_registry.get(
            entitlement_id=(
                binding.commercial_entitlement_id
            )
        )

        if entitlement is None:
            raise RuntimeError(
                "Commercial entitlement is missing."
            )

        billing_cycle_baseline = (
            self._current_billing_cycle_service.resolve_current(
                customer_id=binding.customer_id
            )
        )

        external_funding_observations = (
            self._external_funding_store
            .list_by_cycle_and_account(
                cycle_id=billing_cycle_baseline.cycle_id,
                account_fingerprint=(
                    binding.account_fingerprint
                ),
            )
        )

        return self._capacity_decision_service.decide(
            entitlement=entitlement,
            deployment_binding=binding,
            billing_cycle_baseline=billing_cycle_baseline,
            external_funding_observations=(
                external_funding_observations
            ),
        )
