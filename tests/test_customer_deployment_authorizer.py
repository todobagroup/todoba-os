"""
TODOBA Customer Deployment Authorizer Tests

Security proof:
- authenticated CustomerIdentity is required
- deployment_id is the only customer-selected resource identifier
- customer_id and agent_id are never caller authorization inputs
- ownership truth comes only from CustomerDeploymentRegistry
- owned deployment returns the authoritative CustomerDeployment
- cross-customer and unknown deployments fail closed
- malformed deployment identifiers fail closed
- authoritative agent_id comes only from the deployment record
- registry persistence and restart preserve ownership behavior
- authorization never mutates durable deployment truth
- no HTTP, credential, entitlement, secret, or package boundary
  belongs to this owner

All durable test state is isolated beneath pytest tmp_path.
"""

from inspect import signature
from pathlib import Path

import pytest

from backend.commercial.customer_deployment_authorizer import (
    CustomerDeploymentAuthorizer,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
)


def build_registry(
    tmp_path: Path,
) -> tuple[
    CustomerDeploymentRegistry,
    CustomerDeployment,
    CustomerDeployment,
    CustomerDeployment,
]:
    registry = CustomerDeploymentRegistry(
        tmp_path
        / "customer_deployments.json"
    )

    registry.initialize_empty()

    deployment_a = CustomerDeployment(
        customer_id="customer-d3-a",
        deployment_id="deployment-d3-a",
        agent_id="agent-d3-a",
    )

    deployment_a_second = CustomerDeployment(
        customer_id="customer-d3-a",
        deployment_id="deployment-d3-a-second",
        agent_id="agent-d3-a-second",
    )

    deployment_b = CustomerDeployment(
        customer_id="customer-d3-b",
        deployment_id="deployment-d3-b",
        agent_id="agent-d3-b",
    )

    registry.register(
        deployment_a
    )

    registry.register(
        deployment_a_second
    )

    registry.register(
        deployment_b
    )

    return (
        registry,
        deployment_a,
        deployment_a_second,
        deployment_b,
    )


def customer_a() -> CustomerIdentity:
    return CustomerIdentity(
        customer_id="customer-d3-a"
    )


def customer_b() -> CustomerIdentity:
    return CustomerIdentity(
        customer_id="customer-d3-b"
    )


def test_constructor_requires_customer_deployment_registry() -> None:
    with pytest.raises(
        TypeError,
        match="CustomerDeploymentRegistry",
    ):
        CustomerDeploymentAuthorizer(
            deployment_registry=object()
        )


def test_constructor_requires_ready_deployment_registry(
    tmp_path: Path,
) -> None:
    registry = CustomerDeploymentRegistry(
        tmp_path
        / "customer_deployments.json"
    )

    assert registry.is_ready() is False

    with pytest.raises(
        ValueError,
        match="ready",
    ):
        CustomerDeploymentAuthorizer(
            deployment_registry=registry
        )


def test_authorize_signature_has_only_authenticated_customer_and_deployment_id(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    parameters = tuple(
        signature(
            authorizer.authorize
        ).parameters
    )

    assert parameters == (
        "authenticated_customer",
        "deployment_id",
    )

    assert "customer_id" not in parameters
    assert "agent_id" not in parameters
    assert "authorization" not in parameters
    assert "access_credential" not in parameters
    assert "entitlement" not in parameters
    assert "package_id" not in parameters


def test_owned_deployment_is_authorized(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployment_a,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    result = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_a.deployment_id,
    )

    assert result is deployment_a


def test_authorized_deployment_contains_authoritative_agent_id(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployment_a,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    result = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_a.deployment_id,
    )

    assert result is not None
    assert result.agent_id == deployment_a.agent_id
    assert result.agent_id == "agent-d3-a"


def test_one_customer_can_authorize_multiple_owned_deployments(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployment_a,
        deployment_a_second,
        _,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    identity = customer_a()

    first = authorizer.authorize(
        authenticated_customer=identity,
        deployment_id=deployment_a.deployment_id,
    )

    second = authorizer.authorize(
        authenticated_customer=identity,
        deployment_id=(
            deployment_a_second.deployment_id
        ),
    )

    assert first is deployment_a
    assert second is deployment_a_second


def test_cross_customer_deployment_is_denied(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        _,
        deployment_b,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    result = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_b.deployment_id,
    )

    assert result is None


def test_reverse_cross_customer_deployment_is_denied(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployment_a,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    result = authorizer.authorize(
        authenticated_customer=customer_b(),
        deployment_id=deployment_a.deployment_id,
    )

    assert result is None


def test_unknown_deployment_is_denied(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    result = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id="deployment-does-not-exist",
    )

    assert result is None


@pytest.mark.parametrize(
    "deployment_id",
    (
        "",
        "   ",
        None,
        123,
        object(),
    ),
)
def test_malformed_deployment_id_fails_closed(
    tmp_path: Path,
    deployment_id,
) -> None:
    (
        registry,
        _,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    result = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_id,
    )

    assert result is None


@pytest.mark.parametrize(
    "authenticated_customer",
    (
        None,
        "customer-d3-a",
        123,
        object(),
    ),
)
def test_invalid_authenticated_customer_fails_closed(
    tmp_path: Path,
    authenticated_customer,
) -> None:
    (
        registry,
        deployment_a,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    result = authorizer.authorize(
        authenticated_customer=authenticated_customer,
        deployment_id=deployment_a.deployment_id,
    )

    assert result is None


def test_equivalent_authoritative_customer_identity_is_sufficient(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployment_a,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    authenticated_identity = CustomerIdentity(
        customer_id=deployment_a.customer_id
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    result = authorizer.authorize(
        authenticated_customer=authenticated_identity,
        deployment_id=deployment_a.deployment_id,
    )

    assert result is deployment_a


def test_authorizer_uses_authoritative_registry_lookup_by_deployment_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        registry,
        deployment_a,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    seen = []

    original_get = CustomerDeploymentRegistry.get

    def recording_get(
        self,
        *,
        deployment_id: str,
    ):
        seen.append(
            deployment_id
        )

        return original_get(
            self,
            deployment_id=deployment_id,
        )

    monkeypatch.setattr(
        CustomerDeploymentRegistry,
        "get",
        recording_get,
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    result = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_a.deployment_id,
    )

    assert result is deployment_a

    assert seen == [
        deployment_a.deployment_id
    ]


def test_owned_deployment_authorization_survives_registry_restart(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployment_a,
        _,
        _,
    ) = build_registry(
        tmp_path
    )

    storage_path = registry.storage_path

    restarted = CustomerDeploymentRegistry(
        storage_path
    )

    assert restarted.is_ready() is True

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=restarted
    )

    result = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_a.deployment_id,
    )

    assert result == deployment_a
    assert result is not None
    assert result.agent_id == deployment_a.agent_id


def test_cross_customer_denial_survives_registry_restart(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        _,
        deployment_b,
    ) = build_registry(
        tmp_path
    )

    restarted = CustomerDeploymentRegistry(
        registry.storage_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=restarted
    )

    result = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_b.deployment_id,
    )

    assert result is None


def test_authorization_never_mutates_durable_deployment_truth(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployment_a,
        _,
        deployment_b,
    ) = build_registry(
        tmp_path
    )

    storage_path = registry.storage_path
    before = storage_path.read_bytes()

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    owned = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_a.deployment_id,
    )

    assert owned is deployment_a

    assert storage_path.read_bytes() == before

    denied = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_b.deployment_id,
    )

    assert denied is None

    assert storage_path.read_bytes() == before

    unknown = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id="deployment-unknown",
    )

    assert unknown is None

    assert storage_path.read_bytes() == before


def test_authorization_never_changes_registry_size(
    tmp_path: Path,
) -> None:
    (
        registry,
        deployment_a,
        _,
        deployment_b,
    ) = build_registry(
        tmp_path
    )

    before = registry.size()

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    assert (
        authorizer.authorize(
            authenticated_customer=customer_a(),
            deployment_id=deployment_a.deployment_id,
        )
        is deployment_a
    )

    assert (
        authorizer.authorize(
            authenticated_customer=customer_a(),
            deployment_id=deployment_b.deployment_id,
        )
        is None
    )

    assert registry.size() == before


def test_unknown_and_cross_customer_share_fail_closed_result(
    tmp_path: Path,
) -> None:
    (
        registry,
        _,
        _,
        deployment_b,
    ) = build_registry(
        tmp_path
    )

    authorizer = CustomerDeploymentAuthorizer(
        deployment_registry=registry
    )

    cross_customer = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id=deployment_b.deployment_id,
    )

    unknown = authorizer.authorize(
        authenticated_customer=customer_a(),
        deployment_id="deployment-not-present",
    )

    assert cross_customer is None
    assert unknown is None
    assert cross_customer is unknown
