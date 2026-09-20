"""
TODOBA Customer Commercial External Funding Convergence.

Authenticated Trusted Agent raw MT5 cashflow evidence
is converged into authoritative commercial funding truth.

Caller authority is limited to:
- authenticated agent identity
- raw broker evidence

Commercial deployment, billing cycle, classification,
and durable commercial funding truth remain server-owned.
"""

from backend.commercial.customer_commercial_capacity_decision_provider import (
    CustomerCommercialCapacityDecisionProvider,
)
from backend.commercial.customer_commercial_capacity_decision_service import (
    CustomerCommercialCapacityDecisionStatus,
)
from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBindingStore,
)
from backend.commercial.customer_commercial_external_funding_observation_service import (
    CustomerCommercialExternalFundingObservationRecord,
    CustomerCommercialExternalFundingObservationService,
)
from backend.commercial.customer_commercial_pending_exposure_containment_service import (
    CustomerCommercialPendingExposureContainmentService,
)
from backend.trading.lifecycle.mt5_account_cashflow_history_reader import (
    MT5AccountCashflowEvidence,
)
from backend.trading.lifecycle.mt5_external_funding_classifier import (
    MT5ExternalFundingClassifier,
)


class CustomerCommercialExternalFundingConvergenceService:
    """
    Converge authenticated raw broker evidence into durable
    commercial external-funding truth.
    """

    def __init__(
        self,
        *,
        deployment_binding_store: CustomerCommercialDeploymentBindingStore,
        capacity_decision_provider: CustomerCommercialCapacityDecisionProvider,
        external_funding_classifier: MT5ExternalFundingClassifier,
        observation_service: CustomerCommercialExternalFundingObservationService,
        pending_exposure_containment_service: CustomerCommercialPendingExposureContainmentService,
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
            external_funding_classifier,
            MT5ExternalFundingClassifier,
        ):
            raise TypeError(
                "external_funding_classifier must be "
                "MT5ExternalFundingClassifier."
            )

        if not isinstance(
            observation_service,
            CustomerCommercialExternalFundingObservationService,
        ):
            raise TypeError(
                "observation_service must be "
                "CustomerCommercialExternalFundingObservationService."
            )

        if not isinstance(
            pending_exposure_containment_service,
            CustomerCommercialPendingExposureContainmentService,
        ):
            raise TypeError(
                "pending_exposure_containment_service must be "
                "CustomerCommercialPendingExposureContainmentService."
            )

        self._deployment_binding_store = (
            deployment_binding_store
        )
        self._capacity_decision_provider = (
            capacity_decision_provider
        )
        self._external_funding_classifier = (
            external_funding_classifier
        )
        self._observation_service = (
            observation_service
        )
        self._pending_exposure_containment_service = (
            pending_exposure_containment_service
        )

    def converge(
        self,
        *,
        authenticated_agent_id: str,
        evidence: MT5AccountCashflowEvidence,
    ) -> CustomerCommercialExternalFundingObservationRecord:
        if not isinstance(
            authenticated_agent_id,
            str,
        ):
            raise TypeError(
                "authenticated_agent_id must be str."
            )

        normalized_agent_id = (
            authenticated_agent_id.strip()
        )

        if not normalized_agent_id:
            raise ValueError(
                "authenticated_agent_id must not be empty."
            )

        if not isinstance(
            evidence,
            MT5AccountCashflowEvidence,
        ):
            raise TypeError(
                "evidence must be MT5AccountCashflowEvidence."
            )

        binding = (
            self._deployment_binding_store
            .get_by_agent_account(
                agent_id=normalized_agent_id,
                account_fingerprint=(
                    evidence.account_fingerprint
                ),
            )
        )

        if binding is None:
            raise RuntimeError(
                "Authoritative commercial deployment "
                "binding could not be resolved."
            )

        capacity_decision = (
            self._capacity_decision_provider
            .provide(
                deployment_id=binding.deployment_id,
            )
        )

        if (
            capacity_decision.deployment_id
            != binding.deployment_id
        ):
            raise RuntimeError(
                "Commercial capacity deployment "
                "identity is inconsistent."
            )

        if (
            capacity_decision.commercial_entitlement_id
            != binding.commercial_entitlement_id
        ):
            raise RuntimeError(
                "Commercial capacity entitlement "
                "identity is inconsistent."
            )

        classification = (
            self._external_funding_classifier
            .classify(
                evidence=evidence,
            )
        )

        observation = self._observation_service.observe(
            cycle_id=capacity_decision.cycle_id,
            classification=classification,
        )

        if observation.funding_kind != "external_deposit":
            return observation

        post_observation_capacity_decision = (
            self._capacity_decision_provider.provide(
                deployment_id=binding.deployment_id,
            )
        )

        if (
            post_observation_capacity_decision.deployment_id
            != binding.deployment_id
        ):
            raise RuntimeError(
                "Post-observation commercial capacity deployment "
                "identity is inconsistent."
            )

        if (
            post_observation_capacity_decision.commercial_entitlement_id
            != binding.commercial_entitlement_id
        ):
            raise RuntimeError(
                "Post-observation commercial capacity entitlement "
                "identity is inconsistent."
            )

        if (
            post_observation_capacity_decision.cycle_id
            != observation.cycle_id
        ):
            raise RuntimeError(
                "Post-observation commercial capacity cycle "
                "identity is inconsistent."
            )

        if (
            post_observation_capacity_decision.status
            == CustomerCommercialCapacityDecisionStatus.UPGRADE_REQUIRED
        ):
            trigger_id = (
                "external-funding:"
                f"{observation.account_fingerprint}:"
                f"{observation.deal_ticket}"
            )

            self._pending_exposure_containment_service.issue(
                trigger_id=trigger_id,
                deployment_id=binding.deployment_id,
            )

        return observation
