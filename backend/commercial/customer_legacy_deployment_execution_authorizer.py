"""
TODOBA Legacy Deployment Execution Authorizer

Compatibility authority for customer deployments that
were already entitled before production commercial
capacity enforcement became mandatory.

Authority chain:

    agent_id
        -> authoritative CustomerDeployment
        -> explicit legacy compatibility eligibility
        -> authoritative Trusted Agent account binding
        -> ACTIVE deployment-level entitlement
        -> same CustomerDeployment

This owner does not:
- create or mutate deployments
- create or mutate account bindings
- create or mutate entitlements
- create commercial orders
- create payment or settlement truth
- create commercial entitlement or capacity truth
- process broker state
- execute trading missions
"""

from backend.commercial.customer_deployment_entitlement_authorizer import (
    CustomerDeploymentEntitlementAuthorizer,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_legacy_execution_compatibility_registry import (
    CustomerLegacyExecutionCompatibilityRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)


class CustomerLegacyDeploymentExecutionAuthorizer:
    """
    Authorize an existing entitled deployment for legacy
    execution compatibility.
    """

    def __init__(
        self,
        *,
        deployment_registry: CustomerDeploymentRegistry,
        compatibility_registry: CustomerLegacyExecutionCompatibilityRegistry,
        entitlement_authorizer: CustomerDeploymentEntitlementAuthorizer,
        account_binding_guard: TrustedAgentAccountBindingGuard,
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

        if not isinstance(
            entitlement_authorizer,
            CustomerDeploymentEntitlementAuthorizer,
        ):
            raise TypeError(
                "entitlement_authorizer must be "
                "CustomerDeploymentEntitlementAuthorizer."
            )

        if not isinstance(
            account_binding_guard,
            TrustedAgentAccountBindingGuard,
        ):
            raise TypeError(
                "account_binding_guard must be "
                "TrustedAgentAccountBindingGuard."
            )

        self._deployment_registry = deployment_registry
        self._compatibility_registry = compatibility_registry
        self._entitlement_authorizer = entitlement_authorizer
        self._account_binding_guard = account_binding_guard

    def authorize(
        self,
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> CustomerDeployment:
        deployment = (
            self._deployment_registry.get_by_agent_id(
                agent_id=agent_id,
            )
        )

        if deployment is None:
            raise RuntimeError(
                "Legacy execution deployment could not be resolved."
            )

        eligibility = self._compatibility_registry.get(
            deployment_id=deployment.deployment_id,
        )

        if eligibility is None:
            raise RuntimeError(
                "Deployment is not eligible for legacy execution compatibility."
            )

        self._account_binding_guard.require_binding(
            agent_id=deployment.agent_id,
            account_fingerprint=account_fingerprint,
        )

        authorized = (
            self._entitlement_authorizer.authorize(
                authorized_deployment=deployment,
            )
        )

        if authorized is None:
            raise RuntimeError(
                "Legacy execution deployment is not entitled."
            )

        return authorized
