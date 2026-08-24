"""
TODOBA Customer Deployment Authorizer

Owns customer-to-deployment ownership authorization.

Trust boundary:

    authenticated CustomerIdentity
        +
    customer-supplied deployment_id
        -> authoritative CustomerDeploymentRegistry lookup
        -> customer ownership comparison
        -> authoritative CustomerDeployment

Security rules:
- customer_id is never accepted from the caller
- agent_id is never accepted from the caller
- deployment ownership comes only from CustomerDeploymentRegistry
- unknown and cross-customer deployments fail closed
- malformed deployment identifiers fail closed
- successful authorization returns the authoritative deployment
- authoritative agent_id is obtained only from that deployment record

This component does not:
- authenticate customers
- parse HTTP requests or Authorization headers
- issue customer credentials
- authorize entitlement or subscription state
- access deployment secrets
- build or deliver deployment packages
"""

from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)


class CustomerDeploymentAuthorizer:
    """
    Authorize an authenticated customer against one
    authoritative commercial deployment.
    """

    def __init__(
        self,
        *,
        deployment_registry: CustomerDeploymentRegistry,
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

        self._deployment_registry = (
            deployment_registry
        )

    def authorize(
        self,
        *,
        authenticated_customer: CustomerIdentity,
        deployment_id: str,
    ) -> CustomerDeployment | None:
        """
        Return the authoritative deployment only when the
        authenticated customer owns it.
        """

        if not isinstance(
            authenticated_customer,
            CustomerIdentity,
        ):
            return None

        try:
            deployment = (
                self._deployment_registry.get(
                    deployment_id=deployment_id
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if deployment is None:
            return None

        if (
            deployment.customer_id
            != authenticated_customer.customer_id
        ):
            return None

        return deployment
