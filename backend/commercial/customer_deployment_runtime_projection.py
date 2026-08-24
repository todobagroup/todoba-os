"""
TODOBA Customer Deployment Runtime Projection

Projects durable commercial deployment truth into the
existing in-memory trading runtime registries.

Authoritative sources:
- Customer Deployment Registry
- Customer Deployment Secret Store
- Trusted Agent Account Binding Store

Runtime projections:
- Trusted Agent Credential Registry
- Execution Mission Signing Key Registry
- Control Mission Signing Key Registry
- Execution Target Registry

Projection is:
- additive
- idempotent
- repeatable
- fail-closed

The complete commercial snapshot is validated before any
runtime registry is mutated.

This component does not:
- persist commercial deployment state
- generate or rotate secrets
- create account bindings
- remove or revoke runtime registrations
- own enrollment or customer lifecycle
- own runtime process composition
"""

from dataclasses import dataclass
import hmac

from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
    CustomerDeploymentSecretStore,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTarget,
    ExecutionTargetRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)


@dataclass(
    frozen=True,
    repr=False,
)
class _PreparedDeploymentProjection:
    deployment_id: str
    agent_id: str
    account_fingerprint: str
    secrets: CustomerDeploymentSecrets

    def __repr__(
        self,
    ) -> str:
        return (
            "_PreparedDeploymentProjection("
            f"deployment_id={self.deployment_id!r}, "
            f"agent_id={self.agent_id!r}, "
            f"account_fingerprint="
            f"{self.account_fingerprint!r}, "
            "secret_material=<redacted>)"
        )


class CustomerDeploymentRuntimeProjection:
    """
    Projects complete commercial deployment records into
    existing runtime registries.

    One projection joins:

        deployment_id
            -> agent_id
            -> account_fingerprint

        deployment_id
            -> agent_secret
            -> execution signing secret
            -> control signing secret

    All durable source records and all existing runtime
    conflicts are validated before registration begins.
    """

    def __init__(
        self,
        *,
        deployment_registry: CustomerDeploymentRegistry,
        secret_store: CustomerDeploymentSecretStore,
        account_binding_store: (
            TrustedAgentAccountBindingStore
        ),
        credential_registry: (
            TrustedAgentCredentialRegistry
        ),
        execution_signing_key_registry: (
            TrustedAgentSigningKeyRegistry
        ),
        control_signing_key_registry: (
            TrustedAgentSigningKeyRegistry
        ),
        execution_target_registry: (
            ExecutionTargetRegistry
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
            credential_registry,
            TrustedAgentCredentialRegistry,
        ):
            raise TypeError(
                "credential_registry must be "
                "TrustedAgentCredentialRegistry."
            )

        if not isinstance(
            execution_signing_key_registry,
            TrustedAgentSigningKeyRegistry,
        ):
            raise TypeError(
                "execution_signing_key_registry must be "
                "TrustedAgentSigningKeyRegistry."
            )

        if not isinstance(
            control_signing_key_registry,
            TrustedAgentSigningKeyRegistry,
        ):
            raise TypeError(
                "control_signing_key_registry must be "
                "TrustedAgentSigningKeyRegistry."
            )

        if (
            execution_signing_key_registry
            is control_signing_key_registry
        ):
            raise ValueError(
                "Execution and control signing registries "
                "must be separate security domains."
            )

        if not isinstance(
            execution_target_registry,
            ExecutionTargetRegistry,
        ):
            raise TypeError(
                "execution_target_registry must be "
                "ExecutionTargetRegistry."
            )

        self._deployment_registry = (
            deployment_registry
        )
        self._secret_store = secret_store
        self._account_binding_store = (
            account_binding_store
        )

        self._credential_registry = (
            credential_registry
        )
        self._execution_signing_key_registry = (
            execution_signing_key_registry
        )
        self._control_signing_key_registry = (
            control_signing_key_registry
        )
        self._execution_target_registry = (
            execution_target_registry
        )

    def validate_candidate_runtime_compatibility(
        self,
        *,
        deployment_id: str,
        agent_id: str,
        account_fingerprint: str,
        secrets: CustomerDeploymentSecrets,
    ) -> None:
        """
        Validate one not-yet-committed commercial
        deployment against the current runtime.

        This method is read-only. It exists so enrollment
        can detect runtime credential, signing-key, and
        execution-target conflicts before durable
        activation begins.
        """

        if not isinstance(
            secrets,
            CustomerDeploymentSecrets,
        ):
            raise TypeError(
                "secrets must be "
                "CustomerDeploymentSecrets."
            )

        normalized_values: dict[str, str] = {}

        for name, value in (
            (
                "deployment_id",
                deployment_id,
            ),
            (
                "agent_id",
                agent_id,
            ),
            (
                "account_fingerprint",
                account_fingerprint,
            ),
        ):
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

            normalized_values[name] = (
                normalized
            )

        if (
            secrets.deployment_id
            != normalized_values[
                "deployment_id"
            ]
        ):
            raise ValueError(
                "Customer deployment secret identity "
                "does not match runtime candidate."
            )

        candidate = _PreparedDeploymentProjection(
            deployment_id=(
                normalized_values[
                    "deployment_id"
                ]
            ),
            agent_id=(
                normalized_values[
                    "agent_id"
                ]
            ),
            account_fingerprint=(
                normalized_values[
                    "account_fingerprint"
                ]
            ),
            secrets=secrets,
        )

        self._validate_runtime_conflicts(
            candidate
        )

    def project(
        self,
    ) -> int:
        """
        Reconcile all commercial deployments into runtime.

        Returns the number of complete commercial
        deployments represented by the projection.

        The method may be called repeatedly.

        Existing identical runtime registrations are
        accepted idempotently. Any missing durable source
        or conflicting runtime registration fails before
        this call mutates any runtime registry.
        """

        self._require_sources_ready()

        deployments = (
            self._deployment_registry.all()
        )

        prepared: list[
            _PreparedDeploymentProjection
        ] = []

        for deployment in deployments:
            secrets = self._secret_store.get(
                deployment_id=(
                    deployment.deployment_id
                )
            )

            if secrets is None:
                raise RuntimeError(
                    "Customer deployment secret material "
                    "is missing for runtime projection."
                )

            if (
                secrets.deployment_id
                != deployment.deployment_id
            ):
                raise RuntimeError(
                    "Customer deployment secret identity "
                    "does not match deployment identity."
                )

            account_fingerprint = (
                self._account_binding_store
                .get_account_fingerprint(
                    agent_id=deployment.agent_id
                )
            )

            if account_fingerprint is None:
                raise RuntimeError(
                    "Trusted Agent account binding is "
                    "missing for runtime projection."
                )

            item = _PreparedDeploymentProjection(
                deployment_id=(
                    deployment.deployment_id
                ),
                agent_id=deployment.agent_id,
                account_fingerprint=(
                    account_fingerprint
                ),
                secrets=secrets,
            )

            self._validate_runtime_conflicts(
                item
            )

            prepared.append(
                item
            )

        for item in prepared:
            self._project_prepared_deployment(
                item
            )

        return len(
            prepared
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._deployment_registry.is_ready():
            raise RuntimeError(
                "Customer deployment registry is not "
                "initialized for runtime projection."
            )

        if not self._secret_store.is_ready():
            raise RuntimeError(
                "Customer deployment secret store is not "
                "initialized for runtime projection."
            )

        if not self._account_binding_store.is_ready():
            raise RuntimeError(
                "Trusted Agent account binding store is "
                "not initialized for runtime projection."
            )

    def _validate_runtime_conflicts(
        self,
        item: _PreparedDeploymentProjection,
    ) -> None:
        existing_agent_secret = (
            self._credential_registry.get_secret(
                agent_id=item.agent_id
            )
        )

        if (
            existing_agent_secret is not None
            and not self._same_secret(
                existing_agent_secret,
                item.secrets.agent_secret,
            )
        ):
            raise ValueError(
                "Trusted Agent runtime credential "
                "conflicts with commercial deployment."
            )

        existing_execution_secret = (
            self._execution_signing_key_registry
            .get_secret(
                agent_id=item.agent_id
            )
        )

        if (
            existing_execution_secret is not None
            and not self._same_secret(
                existing_execution_secret,
                item.secrets
                .execution_mission_signing_secret,
            )
        ):
            raise ValueError(
                "Execution signing runtime key "
                "conflicts with commercial deployment."
            )

        existing_control_secret = (
            self._control_signing_key_registry
            .get_secret(
                agent_id=item.agent_id
            )
        )

        if (
            existing_control_secret is not None
            and not self._same_secret(
                existing_control_secret,
                item.secrets
                .control_mission_signing_secret,
            )
        ):
            raise ValueError(
                "Control signing runtime key "
                "conflicts with commercial deployment."
            )

        candidate_target = ExecutionTarget(
            agent_id=item.agent_id,
            account_fingerprint=(
                item.account_fingerprint
            ),
        )

        existing_target = (
            self._execution_target_registry.get(
                agent_id=item.agent_id
            )
        )

        if (
            existing_target is not None
            and existing_target
            != candidate_target
        ):
            raise ValueError(
                "Execution target runtime registration "
                "conflicts with commercial deployment."
            )

    def _project_prepared_deployment(
        self,
        item: _PreparedDeploymentProjection,
    ) -> None:
        self._credential_registry.register(
            agent_id=item.agent_id,
            agent_secret=(
                item.secrets.agent_secret
            ),
        )

        self._execution_signing_key_registry.register(
            agent_id=item.agent_id,
            signing_secret=(
                item.secrets
                .execution_mission_signing_secret
            ),
        )

        self._control_signing_key_registry.register(
            agent_id=item.agent_id,
            signing_secret=(
                item.secrets
                .control_mission_signing_secret
            ),
        )

        self._execution_target_registry.register(
            ExecutionTarget(
                agent_id=item.agent_id,
                account_fingerprint=(
                    item.account_fingerprint
                ),
            )
        )

    @staticmethod
    def _same_secret(
        first: str,
        second: str,
    ) -> bool:
        return hmac.compare_digest(
            first.encode(
                "utf-8"
            ),
            second.encode(
                "utf-8"
            ),
        )