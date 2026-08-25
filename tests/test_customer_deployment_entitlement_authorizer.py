import pytest

from backend.commercial.customer_deployment_entitlement_authorizer import (
    CustomerDeploymentEntitlementAuthorizer,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)


def build_deployment(
    *,
    customer_id: str = "customer-001",
    deployment_id: str = "deployment-001",
    agent_id: str = "trusted-agent-001",
) -> CustomerDeployment:
    return CustomerDeployment(
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
    )


def build_registries(
    tmp_path,
):
    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "customer_deployments.json"
    )
    deployment_registry.initialize_empty()

    entitlement_registry = (
        CustomerDeploymentEntitlementRegistry(
            tmp_path
            / "customer_deployment_entitlements.json",
            deployment_registry=deployment_registry,
        )
    )
    entitlement_registry.initialize_empty()

    return (
        deployment_registry,
        entitlement_registry,
    )


def test_authorizer_requires_entitlement_registry(
    tmp_path,
) -> None:
    with pytest.raises(
        TypeError,
        match="entitlement_registry",
    ):
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=object(),
        )


def test_authorizer_requires_ready_entitlement_registry(
    tmp_path,
) -> None:
    deployment_registry = CustomerDeploymentRegistry(
        tmp_path / "customer_deployments.json"
    )
    deployment_registry.initialize_empty()

    entitlement_registry = (
        CustomerDeploymentEntitlementRegistry(
            tmp_path
            / "customer_deployment_entitlements.json",
            deployment_registry=deployment_registry,
        )
    )

    assert not entitlement_registry.is_ready()

    with pytest.raises(
        ValueError,
        match="entitlement_registry must be ready",
    ):
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=entitlement_registry,
        )


def test_non_customer_deployment_fails_closed(
    tmp_path,
) -> None:
    (
        _deployment_registry,
        entitlement_registry,
    ) = build_registries(
        tmp_path
    )

    authorizer = (
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=entitlement_registry,
        )
    )

    assert (
        authorizer.authorize(
            authorized_deployment=object(),
        )
        is None
    )


def test_no_entitlement_record_fails_closed(
    tmp_path,
) -> None:
    (
        deployment_registry,
        entitlement_registry,
    ) = build_registries(
        tmp_path
    )

    deployment = build_deployment()

    deployment_registry.register(
        deployment
    )

    authorizer = (
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=entitlement_registry,
        )
    )

    assert (
        authorizer.authorize(
            authorized_deployment=deployment,
        )
        is None
    )


def test_active_entitlement_returns_same_deployment(
    tmp_path,
) -> None:
    (
        deployment_registry,
        entitlement_registry,
    ) = build_registries(
        tmp_path
    )

    deployment = build_deployment()

    deployment_registry.register(
        deployment
    )

    entitlement_registry.activate(
        deployment_id=deployment.deployment_id
    )

    authorizer = (
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=entitlement_registry,
        )
    )

    result = authorizer.authorize(
        authorized_deployment=deployment,
    )

    assert result is deployment


def test_suspended_entitlement_fails_closed(
    tmp_path,
) -> None:
    (
        deployment_registry,
        entitlement_registry,
    ) = build_registries(
        tmp_path
    )

    deployment = build_deployment()

    deployment_registry.register(
        deployment
    )

    entitlement_registry.activate(
        deployment_id=deployment.deployment_id
    )

    entitlement_registry.suspend(
        deployment_id=deployment.deployment_id
    )

    authorizer = (
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=entitlement_registry,
        )
    )

    assert (
        authorizer.authorize(
            authorized_deployment=deployment,
        )
        is None
    )


def test_reactivated_entitlement_authorizes_again(
    tmp_path,
) -> None:
    (
        deployment_registry,
        entitlement_registry,
    ) = build_registries(
        tmp_path
    )

    deployment = build_deployment()

    deployment_registry.register(
        deployment
    )

    entitlement_registry.activate(
        deployment_id=deployment.deployment_id
    )

    entitlement_registry.suspend(
        deployment_id=deployment.deployment_id
    )

    entitlement_registry.activate(
        deployment_id=deployment.deployment_id
    )

    authorizer = (
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=entitlement_registry,
        )
    )

    assert (
        authorizer.authorize(
            authorized_deployment=deployment,
        )
        is deployment
    )


def test_entitlement_is_isolated_by_deployment_id(
    tmp_path,
) -> None:
    (
        deployment_registry,
        entitlement_registry,
    ) = build_registries(
        tmp_path
    )

    first = build_deployment(
        customer_id="customer-001",
        deployment_id="deployment-001",
        agent_id="trusted-agent-001",
    )

    second = build_deployment(
        customer_id="customer-001",
        deployment_id="deployment-002",
        agent_id="trusted-agent-002",
    )

    deployment_registry.register(
        first
    )
    deployment_registry.register(
        second
    )

    entitlement_registry.activate(
        deployment_id=first.deployment_id
    )

    authorizer = (
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=entitlement_registry,
        )
    )

    assert (
        authorizer.authorize(
            authorized_deployment=first,
        )
        is first
    )

    assert (
        authorizer.authorize(
            authorized_deployment=second,
        )
        is None
    )