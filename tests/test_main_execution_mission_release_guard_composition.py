"""
TODOBA Main Execution Mission Release Guard Composition Tests

CAP 3I Owner 3 proof:

Production composition must:

- create one ExecutionMissionReleaseGuard
- use the production BrokerStateStore
- use the authoritative account binding guard
- preserve the 30-second Broker State freshness contract
- wire the exact guard into /missions/next
"""

from fastapi.testclient import TestClient

from backend import main
from backend.trading.execution.execution_mission_release_guard import (
    ExecutionMissionReleaseGuard,
)


def test_main_composes_execution_mission_release_guard(
) -> None:
    assert isinstance(
        main.execution_mission_release_guard,
        ExecutionMissionReleaseGuard,
    )

    assert (
        main.execution_mission_release_guard
        .broker_state_store
        is main.broker_state_store
    )

    assert (
        main.execution_mission_release_guard
        .account_binding_guard
        is main.trusted_agent_account_binding_guard
    )

    assert (
        main.execution_mission_release_guard
        .max_age_seconds
        == 30.0
    )


def test_main_execution_mission_router_uses_release_guard(
    monkeypatch,
) -> None:
    deployments = (
        main.customer_deployment_registry.all()
    )

    assert deployments

    deployment = deployments[0]

    secrets = (
        main.customer_deployment_secret_store.get(
            deployment_id=(
                deployment.deployment_id
            )
        )
    )

    assert secrets is not None

    agent_id = deployment.agent_id
    agent_secret = secrets.agent_secret

    target = (
        main.execution_target_registry.get(
            agent_id=agent_id
        )
    )

    assert target is not None

    account_fingerprint = (
        main.trusted_agent_account_binding_store
        .get_account_fingerprint(
            agent_id=agent_id
        )
    )

    assert account_fingerprint is not None

    assert (
        target.account_fingerprint
        == account_fingerprint
    )

    guarded_agents: list[str] = []

    def deny_release(
        *,
        agent_id: str,
    ):
        guarded_agents.append(
            agent_id
        )

        raise RuntimeError(
            "proof Agent is not ready"
        )

    monkeypatch.setattr(
        main.execution_mission_release_guard,
        "require_ready",
        deny_release,
    )

    queued_before = (
        main.execution_mission_store.size()
    )

    client = TestClient(
        main.app
    )

    response = client.get(
        "/missions/next",
        headers={
            "X-TODOBA-Agent-ID": agent_id,
            "Authorization": (
                f"Bearer {agent_secret}"
            ),
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "empty",
        "mission": None,
    }

    assert guarded_agents == [
        agent_id
    ]

    assert (
        main.execution_mission_store.size()
        == queued_before
    )
