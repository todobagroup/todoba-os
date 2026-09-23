from types import SimpleNamespace
import inspect

import pytest

from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationStatus,
)
from backend.commercial.customer_setup_continuity_recovery_service import (
    CustomerSetupContinuityRecoveryService,
)


DEPLOYMENT_ID = "deployment-recovery-001"
CUSTOMER_ID = "customer-recovery-001"
AGENT_ID = "trusted-agent-recovery-001"
ACCOUNT_FINGERPRINT = "XM-Test:123456"


class _DeploymentRegistry:
    def __init__(self, deployment=None):
        self.deployment = deployment

    def get(self, *, deployment_id):
        if (
            self.deployment is not None
            and self.deployment.deployment_id == deployment_id
        ):
            return self.deployment
        return None


class _EntitlementRegistry:
    def __init__(self, active=True):
        self.active = active
        self.calls = []

    def is_active(self, *, deployment_id):
        self.calls.append(deployment_id)
        return self.active


class _AccountBindingStore:
    def __init__(self, fingerprint=ACCOUNT_FINGERPRINT):
        self.fingerprint = fingerprint
        self.calls = []

    def get_account_fingerprint(self, *, agent_id):
        self.calls.append(agent_id)
        return self.fingerprint


class _ActivationStore:
    def __init__(self, owner=None):
        self.owner = owner
        self.calls = []

    def get_by_deployment_id(self, *, deployment_id):
        self.calls.append(deployment_id)
        return self.owner


class _ActivationService:
    def __init__(self):
        self.activate_calls = []
        self.bind_calls = []
        self.activation = SimpleNamespace(
            activation_request_id=(
                f"setup-continuity-recovery:{DEPLOYMENT_ID}"
            ),
            setup_activation_id="setup-activation-recovery-001",
            customer_id=CUSTOMER_ID,
            status=CustomerSetupActivationStatus.ACTIVE,
            deployment_id=None,
        )

    def activate(self, *, activation_request_id, customer_id):
        self.activate_calls.append(
            (activation_request_id, customer_id)
        )
        return self.activation

    def bind(self, *, setup_activation_id, deployment_id):
        self.bind_calls.append(
            (setup_activation_id, deployment_id)
        )
        self.activation = SimpleNamespace(
            activation_request_id=(
                self.activation.activation_request_id
            ),
            setup_activation_id=setup_activation_id,
            customer_id=self.activation.customer_id,
            status=CustomerSetupActivationStatus.BOUND,
            deployment_id=deployment_id,
        )
        return self.activation


class _AccessCodeService:
    def __init__(self):
        self.calls = []
        self.counter = 0

    def reissue_bound(self, *, setup_activation_id):
        self.calls.append(setup_activation_id)
        self.counter += 1
        return SimpleNamespace(
            access_code_id=f"recovery-code-{self.counter}",
            setup_activation_id=setup_activation_id,
            customer_id=CUSTOMER_ID,
            activation_code=f"activation-code-{self.counter}",
        )


def _build_service(
    *,
    deployment=None,
    entitled=True,
    account_fingerprint=ACCOUNT_FINGERPRINT,
    existing_activation=None,
):
    if deployment is None:
        deployment = SimpleNamespace(
            deployment_id=DEPLOYMENT_ID,
            customer_id=CUSTOMER_ID,
            agent_id=AGENT_ID,
        )

    deployment_registry = _DeploymentRegistry(deployment)
    entitlement_registry = _EntitlementRegistry(entitled)
    account_binding_store = _AccountBindingStore(
        account_fingerprint
    )
    activation_store = _ActivationStore(existing_activation)
    activation_service = _ActivationService()
    access_code_service = _AccessCodeService()

    service = CustomerSetupContinuityRecoveryService(
        deployment_registry=deployment_registry,
        entitlement_registry=entitlement_registry,
        account_binding_store=account_binding_store,
        activation_store=activation_store,
        activation_service=activation_service,
        access_code_service=access_code_service,
    )

    return (
        service,
        deployment_registry,
        entitlement_registry,
        account_binding_store,
        activation_store,
        activation_service,
        access_code_service,
    )


def test_recovery_has_narrow_authority_surface():
    parameters = inspect.signature(
        CustomerSetupContinuityRecoveryService.recover
    ).parameters

    assert tuple(parameters) == (
        "self",
        "deployment_id",
    )


def test_active_authoritative_deployment_recovers_bound_setup_continuity():
    (
        service,
        _deployment_registry,
        entitlement_registry,
        account_binding_store,
        activation_store,
        activation_service,
        access_code_service,
    ) = _build_service()

    result = service.recover(
        deployment_id=DEPLOYMENT_ID,
    )

    assert entitlement_registry.calls == [DEPLOYMENT_ID]
    assert account_binding_store.calls == [AGENT_ID]
    assert activation_store.calls == [DEPLOYMENT_ID]

    assert activation_service.activate_calls == [
        (
            f"setup-continuity-recovery:{DEPLOYMENT_ID}",
            CUSTOMER_ID,
        )
    ]
    assert activation_service.bind_calls == [
        (
            "setup-activation-recovery-001",
            DEPLOYMENT_ID,
        )
    ]
    assert access_code_service.calls == [
        "setup-activation-recovery-001"
    ]

    assert result.customer_id == CUSTOMER_ID
    assert result.deployment_id == DEPLOYMENT_ID
    assert result.agent_id == AGENT_ID
    assert result.account_fingerprint == ACCOUNT_FINGERPRINT
    assert (
        result.setup_activation_id
        == "setup-activation-recovery-001"
    )
    assert result.activation_code == "activation-code-1"


def test_missing_deployment_fails_closed_before_mutation():
    (
        service,
        _deployment_registry,
        entitlement_registry,
        account_binding_store,
        activation_store,
        activation_service,
        access_code_service,
    ) = _build_service(
        deployment=SimpleNamespace(
            deployment_id="different-deployment",
            customer_id=CUSTOMER_ID,
            agent_id=AGENT_ID,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="deployment",
    ):
        service.recover(
            deployment_id=DEPLOYMENT_ID,
        )

    assert entitlement_registry.calls == []
    assert account_binding_store.calls == []
    assert activation_store.calls == []
    assert activation_service.activate_calls == []
    assert activation_service.bind_calls == []
    assert access_code_service.calls == []


def test_inactive_deployment_entitlement_fails_closed_before_setup_mutation():
    (
        service,
        _deployment_registry,
        entitlement_registry,
        account_binding_store,
        activation_store,
        activation_service,
        access_code_service,
    ) = _build_service(
        entitled=False,
    )

    with pytest.raises(
        RuntimeError,
        match="entitlement",
    ):
        service.recover(
            deployment_id=DEPLOYMENT_ID,
        )

    assert entitlement_registry.calls == [DEPLOYMENT_ID]
    assert account_binding_store.calls == []
    assert activation_store.calls == []
    assert activation_service.activate_calls == []
    assert activation_service.bind_calls == []
    assert access_code_service.calls == []


def test_missing_account_binding_fails_closed_before_setup_mutation():
    (
        service,
        _deployment_registry,
        entitlement_registry,
        account_binding_store,
        activation_store,
        activation_service,
        access_code_service,
    ) = _build_service(
        account_fingerprint=None,
    )

    with pytest.raises(
        RuntimeError,
        match="account binding",
    ):
        service.recover(
            deployment_id=DEPLOYMENT_ID,
        )

    assert entitlement_registry.calls == [DEPLOYMENT_ID]
    assert account_binding_store.calls == [AGENT_ID]
    assert activation_store.calls == []
    assert activation_service.activate_calls == []
    assert activation_service.bind_calls == []
    assert access_code_service.calls == []


def test_existing_unrelated_setup_owner_fails_closed_without_rotation():
    existing = SimpleNamespace(
        activation_request_id="original-setup-request",
        setup_activation_id="original-setup-activation",
        customer_id=CUSTOMER_ID,
        status=CustomerSetupActivationStatus.BOUND,
        deployment_id=DEPLOYMENT_ID,
    )

    (
        service,
        _deployment_registry,
        _entitlement_registry,
        _account_binding_store,
        activation_store,
        activation_service,
        access_code_service,
    ) = _build_service(
        existing_activation=existing,
    )

    with pytest.raises(
        RuntimeError,
        match="already.*setup activation|setup activation.*already",
    ):
        service.recover(
            deployment_id=DEPLOYMENT_ID,
        )

    assert activation_store.calls == [DEPLOYMENT_ID]
    assert activation_service.activate_calls == []
    assert activation_service.bind_calls == []
    assert access_code_service.calls == []


def test_retry_reuses_recovery_bound_activation_and_only_rotates_code():
    recovery_request_id = (
        f"setup-continuity-recovery:{DEPLOYMENT_ID}"
    )
    existing = SimpleNamespace(
        activation_request_id=recovery_request_id,
        setup_activation_id="setup-activation-recovery-existing",
        customer_id=CUSTOMER_ID,
        status=CustomerSetupActivationStatus.BOUND,
        deployment_id=DEPLOYMENT_ID,
    )

    (
        service,
        _deployment_registry,
        _entitlement_registry,
        _account_binding_store,
        activation_store,
        activation_service,
        access_code_service,
    ) = _build_service(
        existing_activation=existing,
    )

    result = service.recover(
        deployment_id=DEPLOYMENT_ID,
    )

    assert activation_store.calls == [DEPLOYMENT_ID]
    assert activation_service.activate_calls == []
    assert activation_service.bind_calls == []
    assert access_code_service.calls == [
        "setup-activation-recovery-existing"
    ]

    assert (
        result.setup_activation_id
        == "setup-activation-recovery-existing"
    )
    assert result.customer_id == CUSTOMER_ID
    assert result.deployment_id == DEPLOYMENT_ID
    assert result.agent_id == AGENT_ID
    assert result.account_fingerprint == ACCOUNT_FINGERPRINT
    assert result.activation_code == "activation-code-1"
