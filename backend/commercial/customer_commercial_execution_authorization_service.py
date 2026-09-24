"""
TODOBA Commercial Execution Authorization Service

Owns commercial authorization orchestration for creation
of new execution exposure.

Authority chain:

    agent_id + account_fingerprint
        -> commercial deployment binding
            -> commercial capacity decision
            -> new-exposure authorization
        OR, only when commercial binding is absent:
            -> explicit legacy execution compatibility

This owner preserves the existing commercial-capacity
authorization contract.

This component does not:
- create or mutate commercial bindings
- create or mutate commercial entitlements
- create billing-cycle truth
- process payment or settlement truth
- create or mutate legacy compatibility eligibility
- create or persist execution missions
- execute broker orders
"""

from backend.commercial.customer_commercial_capacity_decision_provider import (
    CustomerCommercialCapacityDecisionProvider,
)
from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBindingStore,
)
from backend.commercial.customer_commercial_new_exposure_authorization_service import (
    CustomerCommercialNewExposureAuthorizationService,
)
from backend.commercial.customer_legacy_deployment_execution_authorizer import (
    CustomerLegacyDeploymentExecutionAuthorizer,
)


class CustomerCommercialExecutionAuthorizationService:
    """
    Authorize execution exposure from authoritative
    commercial capacity truth.
    """

    def __init__(
        self,
        *,
        deployment_binding_store: CustomerCommercialDeploymentBindingStore,
        capacity_decision_provider: CustomerCommercialCapacityDecisionProvider,
        new_exposure_authorizer: CustomerCommercialNewExposureAuthorizationService,
        legacy_execution_authorizer: (
            CustomerLegacyDeploymentExecutionAuthorizer | None
        ) = None,
    ) -> None:
        if not isinstance(
            deployment_binding_store,
            CustomerCommercialDeploymentBindingStore,
        ):
            raise TypeError(
                "deployment_binding_store must be "
                "CustomerCommercialDeploymentBindingStore."
            )

        if not isinstance(
            capacity_decision_provider,
            CustomerCommercialCapacityDecisionProvider,
        ):
            raise TypeError(
                "capacity_decision_provider must be "
                "CustomerCommercialCapacityDecisionProvider."
            )

        if not isinstance(
            new_exposure_authorizer,
            CustomerCommercialNewExposureAuthorizationService,
        ):
            raise TypeError(
                "new_exposure_authorizer must be "
                "CustomerCommercialNewExposureAuthorizationService."
            )

        if (
            legacy_execution_authorizer is not None
            and not isinstance(
                legacy_execution_authorizer,
                CustomerLegacyDeploymentExecutionAuthorizer,
            )
        ):
            raise TypeError(
                "legacy_execution_authorizer must be "
                "CustomerLegacyDeploymentExecutionAuthorizer or None."
            )

        self._deployment_binding_store = (
            deployment_binding_store
        )
        self._capacity_decision_provider = (
            capacity_decision_provider
        )
        self._new_exposure_authorizer = (
            new_exposure_authorizer
        )
        self._legacy_execution_authorizer = (
            legacy_execution_authorizer
        )

    def authorize(
        self,
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> None:
        binding = (
            self._deployment_binding_store
            .get_by_agent_account(
                agent_id=agent_id,
                account_fingerprint=account_fingerprint,
            )
        )

        if binding is None:
            if self._legacy_execution_authorizer is None:
                raise RuntimeError(
                    "Execution mission commercial deployment "
                    "binding could not be resolved."
                )

            self._legacy_execution_authorizer.authorize(
                agent_id=agent_id,
                account_fingerprint=account_fingerprint,
            )
            return None

        capacity_decision = (
            self._capacity_decision_provider.provide(
                deployment_id=binding.deployment_id,
            )
        )

        self._new_exposure_authorizer.authorize(
            capacity_decision=capacity_decision,
        )
