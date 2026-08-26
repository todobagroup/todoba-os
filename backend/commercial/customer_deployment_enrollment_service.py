"""
TODOBA Customer Deployment Enrollment Service

Owns durable preparation and activation of one commercial
customer deployment across the existing persistence owners.

Preparation order:

1. validate the complete candidate before mutation
2. verify the existing runtime projection is healthy
3. validate candidate runtime compatibility
4. persist encrypted deployment secrets
5. persist Trusted Agent account binding
6. leave CustomerDeploymentRegistry unchanged

Activation order:

1. require the candidate to be durably prepared
2. revalidate authoritative durable/runtime compatibility
3. register commercial deployment identity
4. refresh runtime projection

The CustomerDeploymentRegistry is the durable enrollment
activation barrier. Secret material and account binding may
be safely staged before registry registration because all
three stores accept identical retries idempotently.

The legacy enroll() operation remains available and is
defined as prepare() followed immediately by activate().

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
class CustomerDeploymentPreparationResult:
    """
    Safe result of one durable deployment preparation.

    Secret material is intentionally excluded.

    The presence of this result does not mean the deployment
    is active. CustomerDeploymentRegistry remains the
    authoritative activation barrier.
    """

    deployment: CustomerDeployment
    account_fingerprint: str


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
    Coordinate preparation and activation of one customer
    deployment.

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

    def prepare(
        self,
        *,
        deployment: CustomerDeployment,
        secrets: CustomerDeploymentSecrets,
        account_fingerprint: str,
    ) -> CustomerDeploymentPreparationResult:
        """
        Durably stage one deployment without activating it.

        Preparation persists only:
        - deployment secret material
        - Trusted Agent account binding

        CustomerDeploymentRegistry is never mutated here.

        Identical retries are accepted. Identity, secret,
        binding, and runtime conflicts fail closed.
        """

        normalized_account_fingerprint = (
            self._validate_inputs(
                deployment=deployment,
                secrets=secrets,
                account_fingerprint=(
                    account_fingerprint
                ),
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
        # snapshot is healthy before staging a candidate.
        self._runtime_projection.project()

        # The candidate is intentionally not represented by
        # CustomerDeploymentRegistry during preparation.
        # Validate its future runtime identity before any
        # durable staging mutation occurs.
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

        self._secret_store.register(
            secrets
        )

        self._account_binding_store.bind(
            agent_id=deployment.agent_id,
            account_fingerprint=(
                normalized_account_fingerprint
            ),
        )

        # Deliberately no deployment registry write and no
        # projection of the candidate here.
        return CustomerDeploymentPreparationResult(
            deployment=deployment,
            account_fingerprint=(
                normalized_account_fingerprint
            ),
        )

    def activate(
        self,
        *,
        deployment: CustomerDeployment,
        secrets: CustomerDeploymentSecrets,
        account_fingerprint: str,
    ) -> CustomerDeploymentEnrollmentResult:
        """
        Activate one previously prepared deployment.

        CustomerDeploymentRegistry.register() remains the
        durable activation barrier.

        Activation fails closed if the expected staged
        secrets or account binding are absent or conflicting.
        """

        normalized_account_fingerprint = (
            self._validate_inputs(
                deployment=deployment,
                secrets=secrets,
                account_fingerprint=(
                    account_fingerprint
                ),
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

        self._require_prepared_candidate(
            deployment=deployment,
            secrets=secrets,
            account_fingerprint=(
                normalized_account_fingerprint
            ),
        )

        # Preparation and activation may be separated by a
        # package-build interval. Revalidate the currently
        # active commercial graph immediately before the
        # activation barrier.
        self._runtime_projection.project()

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

        # Commercial identity is written last and remains
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

        Backward-compatible contract:

            enroll()
                = prepare()
                + activate()

        Identical retries are accepted.
        """

        preparation = self.prepare(
            deployment=deployment,
            secrets=secrets,
            account_fingerprint=(
                account_fingerprint
            ),
        )

        return self.activate(
            deployment=preparation.deployment,
            secrets=secrets,
            account_fingerprint=(
                preparation.account_fingerprint
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

    def _require_prepared_candidate(
        self,
        *,
        deployment: CustomerDeployment,
        secrets: CustomerDeploymentSecrets,
        account_fingerprint: str,
    ) -> None:
        stored_secrets = (
            self._secret_store.get(
                deployment_id=(
                    deployment.deployment_id
                )
            )
        )

        if stored_secrets is None:
            raise RuntimeError(
                "Customer deployment is not prepared: "
                "secret material is missing."
            )

        if not stored_secrets.same_secret_material(
            secrets
        ):
            raise ValueError(
                "Prepared customer deployment secret "
                "material does not match activation."
            )

        stored_account_fingerprint = (
            self._account_binding_store
            .get_account_fingerprint(
                agent_id=deployment.agent_id
            )
        )

        if stored_account_fingerprint is None:
            raise RuntimeError(
                "Customer deployment is not prepared: "
                "account binding is missing."
            )

        if (
            stored_account_fingerprint
            != account_fingerprint
        ):
            raise ValueError(
                "Prepared customer deployment account "
                "binding does not match activation."
            )

    @classmethod
    def _validate_inputs(
        cls,
        *,
        deployment: CustomerDeployment,
        secrets: CustomerDeploymentSecrets,
        account_fingerprint: str,
    ) -> str:
        if not isinstance(
            deployment,
            CustomerDeployment,
        ):
            raise TypeError(
                "deployment must be CustomerDeployment."
            )

        if not isinstance(
            secrets,
            CustomerDeploymentSecrets,
        ):
            raise TypeError(
                "secrets must be "
                "CustomerDeploymentSecrets."
            )

        return cls._normalize_required_string(
            account_fingerprint,
            name="account_fingerprint",
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