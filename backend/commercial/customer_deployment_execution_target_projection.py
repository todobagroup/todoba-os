"""
TODOBA Customer Deployment Execution Target Projection

Projects durable commercial deployment ownership into the
runtime ExecutionTargetRegistry used by routing-only
processes such as the Telegram REMOTE_VPS Executor.

Durable truth:

CustomerDeploymentRegistry
    deployment_id -> agent_id

TrustedAgentAccountBindingStore
    agent_id -> account_fingerprint

Runtime projection:

ExecutionTargetRegistry
    agent_id -> account_fingerprint

This component intentionally does not depend on:
- customer deployment secrets
- Trusted Agent credentials
- execution mission signing keys
- control mission signing keys
- broker state
- trading execution
"""

from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTarget,
    ExecutionTargetRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


class CustomerDeploymentExecutionTargetProjection:
    """
    Project commercial deployment routing ownership into
    one existing ExecutionTargetRegistry.

    The registry object is never replaced. This matters for
    long-lived runtime owners that already hold a reference
    to the same registry, including dispatch recovery.

    Projection is additive and idempotent.

    Removal, revocation, suspension, and target deletion are
    lifecycle responsibilities outside this capability.
    """

    def __init__(
        self,
        *,
        deployment_registry: CustomerDeploymentRegistry,
        account_binding_store: (
            TrustedAgentAccountBindingStore
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
            account_binding_store,
            TrustedAgentAccountBindingStore,
        ):
            raise TypeError(
                "account_binding_store must be "
                "TrustedAgentAccountBindingStore."
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

        self._account_binding_store = (
            account_binding_store
        )

        self._execution_target_registry = (
            execution_target_registry
        )

    def project(
        self,
    ) -> int:
        """
        Reconcile all durable commercial deployments into
        the existing runtime execution target registry.

        All durable source joins and all existing runtime
        conflicts are validated before any new target is
        registered.

        Returns the number of complete commercial
        deployments represented by this projection.
        """

        self._require_sources_ready()

        deployments = (
            self._deployment_registry.all()
        )

        prepared: list[
            ExecutionTarget
        ] = []

        for deployment in deployments:
            account_fingerprint = (
                self._account_binding_store
                .get_account_fingerprint(
                    agent_id=deployment.agent_id
                )
            )

            if account_fingerprint is None:
                raise RuntimeError(
                    "Trusted Agent account binding is "
                    "missing for execution target "
                    "projection."
                )

            target = ExecutionTarget(
                agent_id=deployment.agent_id,
                account_fingerprint=(
                    account_fingerprint
                ),
            )

            existing = (
                self._execution_target_registry.get(
                    agent_id=target.agent_id
                )
            )

            if (
                existing is not None
                and existing != target
            ):
                raise RuntimeError(
                    "Execution target runtime conflict "
                    "prevents commercial projection."
                )

            prepared.append(
                target
            )

        for target in prepared:
            self._execution_target_registry.register(
                target
            )

        return len(
            prepared
        )

    def _require_sources_ready(
        self,
    ) -> None:
        if not self._deployment_registry.is_ready():
            raise RuntimeError(
                "Customer deployment registry is "
                "not initialized."
            )

        if not self._account_binding_store.is_ready():
            raise RuntimeError(
                "Trusted Agent account binding store "
                "is not initialized."
            )
