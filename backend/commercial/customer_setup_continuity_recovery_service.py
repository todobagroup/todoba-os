"""
TODOBA Customer Setup Continuity Recovery Service.

Recover customer-visible Setup continuity only from an already
authoritative deployment after historical Setup lineage has been lost.

Trust boundary:

    deployment_id
        -> authoritative CustomerDeployment
        -> ACTIVE deployment entitlement
        -> authoritative Trusted Agent account binding
        -> recovery-derived Setup Activation
        -> same deployment binding
        -> fresh BOUND Setup Access Code

This owner deliberately does not create or mutate:
- customer identity
- customer deployment
- Trusted Agent identity
- Trusted Agent account binding
- deployment entitlement
- deployment secret

Historical Setup identities are never fabricated. Recovery creates a new
deterministic recovery lineage tied to the surviving deployment identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
)


_RECOVERY_REQUEST_PREFIX = "setup-continuity-recovery:"


@dataclass(frozen=True)
class CustomerSetupContinuityRecoveryResult:
    customer_id: str
    deployment_id: str
    agent_id: str
    account_fingerprint: str
    setup_activation_id: str
    activation_code: str = field(repr=False)


class CustomerSetupContinuityRecoveryService:
    """
    Reconstruct Setup access authority from surviving deployment truth.

    Caller authority is intentionally limited to deployment_id.
    """

    def __init__(
        self,
        *,
        deployment_registry,
        entitlement_registry,
        account_binding_store,
        activation_store,
        activation_service,
        access_code_service,
    ) -> None:
        self._deployment_registry = deployment_registry
        self._entitlement_registry = entitlement_registry
        self._account_binding_store = account_binding_store
        self._activation_store = activation_store
        self._activation_service = activation_service
        self._access_code_service = access_code_service

    def recover(
        self,
        *,
        deployment_id: str,
    ) -> CustomerSetupContinuityRecoveryResult:
        normalized_deployment_id = self._normalize_required_string(
            deployment_id,
            name="deployment_id",
        )

        deployment = self._deployment_registry.get(
            deployment_id=normalized_deployment_id,
        )

        if deployment is None:
            raise RuntimeError(
                "Authoritative customer deployment does not exist."
            )

        if deployment.deployment_id != normalized_deployment_id:
            raise RuntimeError(
                "Authoritative customer deployment identity mismatch."
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

        recovery_request_id = (
            f"{_RECOVERY_REQUEST_PREFIX}{deployment.deployment_id}"
        )

        existing = self._activation_store.get_by_deployment_id(
            deployment_id=deployment.deployment_id,
        )

        if existing is not None:
            self._require_recovery_owned_bound_activation(
                activation=existing,
                deployment=deployment,
                recovery_request_id=recovery_request_id,
            )

            issuance = self._access_code_service.reissue_bound(
                setup_activation_id=existing.setup_activation_id,
            )

            return self._build_result(
                deployment=deployment,
                account_fingerprint=account_fingerprint,
                setup_activation_id=existing.setup_activation_id,
                issuance=issuance,
            )

        activated = self._activation_service.activate(
            activation_request_id=recovery_request_id,
            customer_id=deployment.customer_id,
        )

        if activated.customer_id != deployment.customer_id:
            raise RuntimeError(
                "Recovery Setup Activation customer identity mismatch."
            )

        if activated.status is CustomerSetupActivationStatus.BOUND:
            if activated.deployment_id != deployment.deployment_id:
                raise RuntimeError(
                    "Recovery Setup Activation deployment identity mismatch."
                )
            bound = activated
        else:
            bound = self._activation_service.bind(
                setup_activation_id=activated.setup_activation_id,
                deployment_id=deployment.deployment_id,
            )

        if (
            bound.status is not CustomerSetupActivationStatus.BOUND
            or bound.deployment_id != deployment.deployment_id
            or bound.customer_id != deployment.customer_id
        ):
            raise RuntimeError(
                "Setup continuity recovery did not finish BOUND."
            )

        issuance = self._access_code_service.reissue_bound(
            setup_activation_id=bound.setup_activation_id,
        )

        return self._build_result(
            deployment=deployment,
            account_fingerprint=account_fingerprint,
            setup_activation_id=bound.setup_activation_id,
            issuance=issuance,
        )

    @staticmethod
    def _require_recovery_owned_bound_activation(
        *,
        activation,
        deployment,
        recovery_request_id: str,
    ) -> None:
        if activation.activation_request_id != recovery_request_id:
            raise RuntimeError(
                "Deployment already has a setup activation owner."
            )

        if (
            activation.status
            is not CustomerSetupActivationStatus.BOUND
            or activation.deployment_id != deployment.deployment_id
            or activation.customer_id != deployment.customer_id
        ):
            raise RuntimeError(
                "Recovery Setup Activation authority is inconsistent."
            )

    @staticmethod
    def _build_result(
        *,
        deployment,
        account_fingerprint: str,
        setup_activation_id: str,
        issuance,
    ) -> CustomerSetupContinuityRecoveryResult:
        if issuance.setup_activation_id != setup_activation_id:
            raise RuntimeError(
                "Setup access-code activation identity mismatch."
            )

        if issuance.customer_id != deployment.customer_id:
            raise RuntimeError(
                "Setup access-code customer identity mismatch."
            )

        return CustomerSetupContinuityRecoveryResult(
            customer_id=deployment.customer_id,
            deployment_id=deployment.deployment_id,
            agent_id=deployment.agent_id,
            account_fingerprint=account_fingerprint,
            setup_activation_id=setup_activation_id,
            activation_code=issuance.activation_code,
        )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} must not be empty."
            )

        if normalized != value:
            raise ValueError(
                f"{name} must be normalized."
            )

        return normalized
