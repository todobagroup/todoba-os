"""
TODOBA Customer Deployment Enrollment Service

Owns one durable commercial enrollment transaction across
the existing deployment persistence owners.

Enrollment order:

1. validate the complete candidate before mutation
2. verify the existing runtime projection is healthy
3. persist encrypted deployment secrets
4. persist Trusted Agent account binding
5. register commercial deployment identity last
6. refresh runtime projection

The CustomerDeploymentRegistry is the durable enrollment
activation barrier. Secret material and account binding may
be safely staged before registry registration because all
three stores accept identical retries idempotently.

This component does not:
- generate customer, deployment, or Agent identities
- generate or rotate secret material
- build Trusted Agent artifacts
- expose an HTTP API
- purchase or migrate MetaTrader Virtual Hosting
- own subscription or entitlement
- remove or revoke deployments
"""

from dataclasses import dataclass

from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_deployment_runtime_projection import (
    CustomerDeploymentRuntimeProjection,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
    CustomerDeploymentSecretStore,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


@dataclass(
    frozen=True,
)
class CustomerDeploymentEnrollmentResult:
    """
    Public result of one completed enrollment.

    Secret material is intentionally excluded.
    """

    deployment: CustomerDeployment
    account_fingerprint: str
    projected_deployment_count: int


class CustomerDeploymentEnrollmentService:
    """
    Coordinate one complete customer deployment enrollment.

    Durable source ownership remains with the existing
    registry, secret store, and account binding store.
    """

    def __init__(
        self,
        *,
        deployment_registry: CustomerDeploymentRegistry,
        secret_store: CustomerDeploymentSecretStore,
        account_binding_store: (
            TrustedAgentAccountBindingStore
        ),
        runtime_projection: (
            CustomerDeploymentRuntimeProjection
        ),
    ) -> None:
        if not isinstance(
            deployment_registry,
            CustomerDeploymentRegistry,
        ):
            raise TypeError(
                "deployment_registry must be "
                "CustomerDeploymentRegistry."
            )

        if not isinstance(
            secret_store,
            CustomerDeploymentSecretStore,
        ):
            raise TypeError(
                "secret_store must be "
                "CustomerDeploymentSecretStore."
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
            runtime_projection,
            CustomerDeploymentRuntimeProjection,
        ):
            raise TypeError(
                "runtime_projection must be "
                "CustomerDeploymentRuntimeProjection."
            )

        self._deployment_registry = (
            deployment_registry
        )

        self._secret_store = (
            secret_store
        )

        self._account_binding_store = (
            account_binding_store
        )

        self._runtime_projection = (
            runtime_projection
        )

    def enroll(
        self,
        *,
        deployment: CustomerDeployment,
        secrets: CustomerDeploymentSecrets,
        account_fingerprint: str,
    ) -> CustomerDeploymentEnrollmentResult:
        """
        Persist and activate one complete commercial
        deployment enrollment.

        Identical retries are accepted.

        Identity, secret, binding, and runtime conflicts
        fail closed.
        """

        if not isinstance(
            deployment,
            CustomerDeployment,
        ):
            raise TypeError(
                "enroll requires CustomerDeployment."
            )

        if not isinstance(
            secrets,
            CustomerDeploymentSecrets,
        ):
            raise TypeError(
                "enroll requires "
                "CustomerDeploymentSecrets."
            )

        normalized_account_fingerprint = (
            self._normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        self._require_sources_ready()

        self._validate_candidate(
            deployment=deployment,
            secrets=secrets,
            account_fingerprint=(
                normalized_account_fingerprint
            ),
        )

        # Verify the currently committed commercial
        # snapshot can still be projected before the new
        # candidate mutates any durable source.
        self._runtime_projection.project()

        # The candidate itself is not yet represented by
        # the durable deployment registry, so validate its
        # runtime compatibility explicitly before any
        # durable source is mutated.
        self._runtime_projection.validate_candidate_runtime_compatibility(
            deployment_id=(
                deployment.deployment_id
            ),
            agent_id=deployment.agent_id,
            account_fingerprint=(
                normalized_account_fingerprint
            ),
            secrets=secrets,
        )

        # Secrets and binding are staged first. Both stores
        # are independently durable and idempotent.
        self._secret_store.register(
            secrets
        )

        self._account_binding_store.bind(
            agent_id=deployment.agent_id,
            account_fingerprint=(
                normalized_account_fingerprint
            ),
        )

        # Commercial identity is written last and acts as
        # the durable activation barrier.
        stored_deployment = (
            self._deployment_registry.register(
                deployment
            )
        )

        projected_count = (
            self._runtime_projection.project()
        )

        return CustomerDeploymentEnrollmentResult(
            deployment=stored_deployment,
            account_fingerprint=(
                normalized_account_fingerprint
            ),
            projected_deployment_count=(
                projected_count
            ),
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._deployment_registry.is_ready():
            raise RuntimeError(
                "Customer deployment registry is not "
                "initialized for enrollment."
            )

        if not self._secret_store.is_ready():
            raise RuntimeError(
                "Customer deployment secret store is not "
                "initialized for enrollment."
            )

        if not self._account_binding_store.is_ready():
            raise RuntimeError(
                "Trusted Agent account binding store is "
                "not initialized for enrollment."
            )

    def _validate_candidate(
        self,
        *,
        deployment: CustomerDeployment,
        secrets: CustomerDeploymentSecrets,
        account_fingerprint: str,
    ) -> None:
        if (
            secrets.deployment_id
            != deployment.deployment_id
        ):
            raise ValueError(
                "Customer deployment secret identity "
                "does not match enrollment deployment."
            )

        existing_deployment = (
            self._deployment_registry.get(
                deployment_id=(
                    deployment.deployment_id
                )
            )
        )

        if (
            existing_deployment is not None
            and existing_deployment != deployment
        ):
            raise ValueError(
                "Customer deployment enrollment "
                "conflicts with existing deployment."
            )

        existing_agent_deployment = (
            self._deployment_registry.get_by_agent_id(
                agent_id=deployment.agent_id
            )
        )

        if (
            existing_agent_deployment is not None
            and existing_agent_deployment != deployment
        ):
            raise ValueError(
                "Trusted Agent identity is already "
                "assigned to another enrollment."
            )

        existing_secrets = (
            self._secret_store.get(
                deployment_id=(
                    deployment.deployment_id
                )
            )
        )

        if (
            existing_secrets is not None
            and not existing_secrets.same_secret_material(
                secrets
            )
        ):
            raise ValueError(
                "Customer deployment enrollment "
                "conflicts with existing secret material."
            )

        existing_account_fingerprint = (
            self._account_binding_store
            .get_account_fingerprint(
                agent_id=deployment.agent_id
            )
        )

        if (
            existing_account_fingerprint is not None
            and existing_account_fingerprint
            != account_fingerprint
        ):
            raise ValueError(
                "Customer deployment enrollment "
                "conflicts with existing account binding."
            )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} is required."
            )

        return normalized
