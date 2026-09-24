"""
TODOBA Legacy Execution Compatibility Recovery Service.

Enroll one existing deployment into explicit legacy
execution compatibility only from surviving authoritative
recovery truth.

Caller authority:
    deployment_id only

Trust chain:
    deployment_id
        -> authoritative CustomerDeployment
        -> ACTIVE deployment entitlement
        -> authoritative Trusted Agent account binding
        -> recovery-owned BOUND Setup activation
        -> explicit compatibility eligibility

This owner does not:
- create or mutate customer deployments
- create or mutate deployment entitlements
- create or mutate Trusted Agent bindings
- create or mutate Setup activations
- process payment, settlement, or commercial capacity
- authorize execution missions
"""

from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_legacy_execution_compatibility_registry import (
    CustomerLegacyExecutionCompatibilityRecord,
    CustomerLegacyExecutionCompatibilityRegistry,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


_RECOVERY_REQUEST_PREFIX = "setup-continuity-recovery:"


class CustomerLegacyExecutionCompatibilityRecoveryService:
    """
    Recover explicit legacy execution compatibility from
    authoritative surviving deployment truth.
    """

    def __init__(
        self,
        *,
        deployment_registry: CustomerDeploymentRegistry,
        entitlement_registry: CustomerDeploymentEntitlementRegistry,
        account_binding_store: TrustedAgentAccountBindingStore,
        activation_store: CustomerSetupActivationStore,
        compatibility_registry: CustomerLegacyExecutionCompatibilityRegistry,
    ) -> None:
        if not isinstance(
            deployment_registry,
            CustomerDeploymentRegistry,
        ):
            raise TypeError(
                "deployment_registry must be "
                "CustomerDeploymentRegistry."
            )

        if not deployment_registry.is_ready():
            raise ValueError(
                "deployment_registry must be ready."
            )

        if not isinstance(
            entitlement_registry,
            CustomerDeploymentEntitlementRegistry,
        ):
            raise TypeError(
                "entitlement_registry must be "
                "CustomerDeploymentEntitlementRegistry."
            )

        if not entitlement_registry.is_ready():
            raise ValueError(
                "entitlement_registry must be ready."
            )

        if not isinstance(
            account_binding_store,
            TrustedAgentAccountBindingStore,
        ):
            raise TypeError(
                "account_binding_store must be "
                "TrustedAgentAccountBindingStore."
            )

        if not account_binding_store.is_ready():
            raise ValueError(
                "account_binding_store must be ready."
            )

        if not isinstance(
            activation_store,
            CustomerSetupActivationStore,
        ):
            raise TypeError(
                "activation_store must be "
                "CustomerSetupActivationStore."
            )

        if not activation_store.is_ready():
            raise ValueError(
                "activation_store must be ready."
            )

        if not isinstance(
            compatibility_registry,
            CustomerLegacyExecutionCompatibilityRegistry,
        ):
            raise TypeError(
                "compatibility_registry must be "
                "CustomerLegacyExecutionCompatibilityRegistry."
            )

        if not compatibility_registry.is_ready():
            raise ValueError(
                "compatibility_registry must be ready."
            )

        self._deployment_registry = deployment_registry
        self._entitlement_registry = entitlement_registry
        self._account_binding_store = account_binding_store
        self._activation_store = activation_store
        self._compatibility_registry = compatibility_registry

    def recover(
        self,
        *,
        deployment_id: str,
    ) -> CustomerLegacyExecutionCompatibilityRecord:
        deployment = self._deployment_registry.get(
            deployment_id=deployment_id,
        )

        if deployment is None:
            raise RuntimeError(
                "Authoritative customer deployment does not exist."
            )

        if not self._entitlement_registry.is_active(
            deployment_id=deployment.deployment_id,
        ):
            raise RuntimeError(
                "ACTIVE customer deployment entitlement is required."
            )

        account_fingerprint = (
            self._account_binding_store.get_account_fingerprint(
                agent_id=deployment.agent_id,
            )
        )

        if account_fingerprint is None:
            raise RuntimeError(
                "Authoritative Trusted Agent account binding is missing."
            )

        activation = self._activation_store.get_by_deployment_id(
            deployment_id=deployment.deployment_id,
        )

        if activation is None:
            raise RuntimeError(
                "Recovery-owned BOUND Setup activation is missing."
            )

        recovery_request_id = (
            f"{_RECOVERY_REQUEST_PREFIX}{deployment.deployment_id}"
        )

        if activation.activation_request_id != recovery_request_id:
            raise RuntimeError(
                "Setup activation is not recovery-owned."
            )

        if (
            activation.status
            is not CustomerSetupActivationStatus.BOUND
        ):
            raise RuntimeError(
                "Recovery-owned Setup activation must be BOUND."
            )

        if activation.deployment_id != deployment.deployment_id:
            raise RuntimeError(
                "Recovery Setup Activation deployment identity mismatch."
            )

        if activation.customer_id != deployment.customer_id:
            raise RuntimeError(
                "Recovery Setup Activation customer identity mismatch."
            )

        return self._compatibility_registry.register(
            CustomerLegacyExecutionCompatibilityRecord(
                deployment_id=deployment.deployment_id,
                setup_activation_id=activation.setup_activation_id,
                recovery_request_id=recovery_request_id,
            )
        )
