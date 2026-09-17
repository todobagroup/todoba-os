from __future__ import annotations

from backend.commercial.customer_commercial_deployment_binding import (
    CustomerCommercialDeploymentBinding,
    CustomerCommercialDeploymentBindingStore,
)
from backend.commercial.customer_commercial_entitlement_registry import (
    CustomerCommercialEntitlementRegistry,
    CustomerCommercialEntitlementStatus,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
    CustomerSetupActivationStore,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


class CustomerCommercialDeploymentConvergenceService:
    """
    Converge existing authoritative commercial, Setup,
    deployment, and MT5 account truths into one immutable
    commercial-deployment binding.

    Caller authority is intentionally limited to:
        commercial_entitlement_id
        setup_activation_id
    """

    def __init__(
        self,
        *,
        entitlement_registry: CustomerCommercialEntitlementRegistry,
        activation_store: CustomerSetupActivationStore,
        deployment_registry: CustomerDeploymentRegistry,
        account_binding_store: TrustedAgentAccountBindingStore,
        binding_store: CustomerCommercialDeploymentBindingStore,
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
            activation_store,
            CustomerSetupActivationStore,
        ):
            raise TypeError(
                "activation_store must be "
                "CustomerSetupActivationStore."
            )

        if not isinstance(
            deployment_registry,
            CustomerDeploymentRegistry,
        ):
            raise TypeError(
                "deployment_registry must be "
                "CustomerDeploymentRegistry."
            )

        if not isinstance(
            account_binding_store,
            TrustedAgentAccountBindingStore,
        ):
            raise TypeError(
                "account_binding_store must be "
                "TrustedAgentAccountBindingStore."
            )

        if not isinstance(
            binding_store,
            CustomerCommercialDeploymentBindingStore,
        ):
            raise TypeError(
                "binding_store must be "
                "CustomerCommercialDeploymentBindingStore."
            )

        if not entitlement_registry.is_ready():
            raise RuntimeError(
                "Commercial entitlement registry is "
                "not initialized."
            )

        if not activation_store.is_ready():
            raise RuntimeError(
                "Customer setup activation store is "
                "not initialized."
            )

        if not deployment_registry.is_ready():
            raise RuntimeError(
                "Customer deployment registry is "
                "not initialized."
            )

        if not account_binding_store.is_ready():
            raise RuntimeError(
                "Trusted Agent account binding store is "
                "not initialized."
            )

        if not binding_store.is_ready():
            raise RuntimeError(
                "Commercial deployment binding store is "
                "not initialized."
            )

        self._entitlement_registry = entitlement_registry
        self._activation_store = activation_store
        self._deployment_registry = deployment_registry
        self._account_binding_store = account_binding_store
        self._binding_store = binding_store

    def converge(
        self,
        *,
        commercial_entitlement_id: str,
        setup_activation_id: str,
    ) -> CustomerCommercialDeploymentBinding:
        entitlement = self._entitlement_registry.get(
            entitlement_id=commercial_entitlement_id
        )

        if entitlement is None:
            raise RuntimeError(
                "Unknown commercial entitlement."
            )

        if (
            entitlement.status
            is not CustomerCommercialEntitlementStatus.ACTIVE
        ):
            raise RuntimeError(
                "P9E2 requires an ACTIVE commercial entitlement."
            )

        activation = self._activation_store.get(
            setup_activation_id=setup_activation_id
        )

        if activation is None:
            raise RuntimeError(
                "Unknown setup activation."
            )

        if (
            activation.status
            is not CustomerSetupActivationStatus.BOUND
            or activation.deployment_id is None
        ):
            raise RuntimeError(
                "P9E2 requires a BOUND setup activation."
            )

        if (
            activation.customer_id
            != entitlement.customer_id
        ):
            raise RuntimeError(
                "Commercial entitlement and setup activation "
                "customer identity do not match."
            )

        deployment = self._deployment_registry.get(
            deployment_id=activation.deployment_id
        )

        if deployment is None:
            raise RuntimeError(
                "Authoritative customer deployment is missing."
            )

        if (
            deployment.deployment_id
            != activation.deployment_id
        ):
            raise RuntimeError(
                "Customer deployment identity is inconsistent."
            )

        if (
            deployment.customer_id
            != entitlement.customer_id
        ):
            raise RuntimeError(
                "Customer deployment belongs to a different "
                "customer."
            )

        account_fingerprint = (
            self._account_binding_store
            .get_account_fingerprint(
                agent_id=deployment.agent_id
            )
        )

        if account_fingerprint is None:
            raise RuntimeError(
                "Authoritative Trusted Agent account binding "
                "is missing."
            )

        binding = CustomerCommercialDeploymentBinding(
            commercial_entitlement_id=(
                entitlement.entitlement_id
            ),
            customer_id=entitlement.customer_id,
            deployment_id=deployment.deployment_id,
            agent_id=deployment.agent_id,
            account_fingerprint=account_fingerprint,
        )

        return self._binding_store.register(
            binding
        )
