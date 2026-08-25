"""
TODOBA Customer Deployment Entitlement Authorizer

Owns commercial entitlement authorization for an already
customer-authorized deployment.

Trust boundary:

    authorized CustomerDeployment from D3
        -> authoritative deployment_id
        -> CustomerDeploymentEntitlementRegistry
        -> ACTIVE returns the same CustomerDeployment
        -> SUSPENDED or no record fails closed

Security rules:
- input must already be an authorized CustomerDeployment from D3
- entitlement identity comes only from deployment.deployment_id
- customer_id is never accepted from the caller
- agent_id is never accepted from the caller
- credentials are never accepted from the caller
- payment or subscription identifiers are never accepted
- HTTP requests are never accepted
- package paths are never accepted
- ACTIVE is the only entitled state
- SUSPENDED and no entitlement record fail closed

This component does not:
- authenticate customers
- authorize customer ownership of deployments
- mutate entitlement state
- process payments or subscriptions
- parse HTTP requests
- access deployment secrets
- build or deliver deployment packages
"""

from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
)


class CustomerDeploymentEntitlementAuthorizer:
    """
    Authorize one already customer-authorized deployment
    against authoritative deployment-level entitlement.
    """

    def __init__(
        self,
        *,
        entitlement_registry: CustomerDeploymentEntitlementRegistry,
    ) -> None:
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

        self._entitlement_registry = (
            entitlement_registry
        )

    def authorize(
        self,
        *,
        authorized_deployment: CustomerDeployment,
    ) -> CustomerDeployment | None:
        """
        Return the already-authorized deployment only when
        its authoritative deployment entitlement is ACTIVE.
        """

        if not isinstance(
            authorized_deployment,
            CustomerDeployment,
        ):
            return None

        if not self._entitlement_registry.is_active(
            deployment_id=(
                authorized_deployment.deployment_id
            )
        ):
            return None

        return authorized_deployment