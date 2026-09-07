import pytest

from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
)
from backend.commercial.customer_vps_connect_deployment_resolver import (
    CustomerVPSConnectDeploymentResolution,
    CustomerVPSConnectDeploymentResolver,
)


class _DeploymentRegistry:
    def __init__(self, deployments):
        self._deployments = tuple(deployments)

    def all(self):
        return self._deployments


class _AccountBindingStore:
    def __init__(self, bindings):
        self._bindings = dict(bindings)

    def get_account_fingerprint(self, *, agent_id):
        return self._bindings.get(agent_id)


def _deployment(customer_id, deployment_id, agent_id):
    return CustomerDeployment(
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
    )


def test_resolves_exact_customer_and_account():
    resolver = CustomerVPSConnectDeploymentResolver(
        deployment_registry=_DeploymentRegistry(
            (
                _deployment(
                    "customer-001",
                    "deployment-001",
                    "trusted-agent-001",
                ),
            )
        ),
        account_binding_store=_AccountBindingStore(
            {
                "trusted-agent-001": "Broker-Pro:12345",
            }
        ),
    )

    result = resolver.resolve(
        customer_id="customer-001",
        account_fingerprint="Broker-Pro:12345",
    )

    assert isinstance(
        result,
        CustomerVPSConnectDeploymentResolution,
    )
    assert result.customer_id == "customer-001"
    assert result.deployment_id == "deployment-001"
    assert result.agent_id == "trusted-agent-001"
    assert result.account_fingerprint == "Broker-Pro:12345"


def test_does_not_cross_customer_authority():
    resolver = CustomerVPSConnectDeploymentResolver(
        deployment_registry=_DeploymentRegistry(
            (
                _deployment(
                    "customer-other",
                    "deployment-other",
                    "trusted-agent-other",
                ),
            )
        ),
        account_binding_store=_AccountBindingStore(
            {
                "trusted-agent-other": "Broker-Pro:12345",
            }
        ),
    )

    assert resolver.resolve(
        customer_id="customer-001",
        account_fingerprint="Broker-Pro:12345",
    ) is None


def test_wrong_account_returns_none():
    resolver = CustomerVPSConnectDeploymentResolver(
        deployment_registry=_DeploymentRegistry(
            (
                _deployment(
                    "customer-001",
                    "deployment-001",
                    "trusted-agent-001",
                ),
            )
        ),
        account_binding_store=_AccountBindingStore(
            {
                "trusted-agent-001": "Broker-Pro:99999",
            }
        ),
    )

    assert resolver.resolve(
        customer_id="customer-001",
        account_fingerprint="Broker-Pro:12345",
    ) is None


def test_multiple_matches_fail_closed():
    resolver = CustomerVPSConnectDeploymentResolver(
        deployment_registry=_DeploymentRegistry(
            (
                _deployment(
                    "customer-001",
                    "deployment-001",
                    "trusted-agent-001",
                ),
                _deployment(
                    "customer-001",
                    "deployment-002",
                    "trusted-agent-002",
                ),
            )
        ),
        account_binding_store=_AccountBindingStore(
            {
                "trusted-agent-001": "Broker-Pro:12345",
                "trusted-agent-002": "Broker-Pro:12345",
            }
        ),
    )

    with pytest.raises(RuntimeError):
        resolver.resolve(
            customer_id="customer-001",
            account_fingerprint="Broker-Pro:12345",
        )
