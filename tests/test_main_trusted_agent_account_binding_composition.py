"""
TODOBA Customer Deployment Runtime Composition Tests

Locks the production API composition for:
- durable customer deployment identity
- encrypted customer deployment secrets
- authoritative Agent-to-account ownership
- runtime credential projection
- runtime execution-target projection
- explicit fail-closed startup refresh
"""

import asyncio

import pytest

from backend import main
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_deployment_runtime_projection import (
    CustomerDeploymentRuntimeProjection,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecretStore,
)
from backend.config import (
    TODOBA_CONTROL_PLANE_DATA_ROOT,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTarget,
    ExecutionTargetRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)
from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
)


def test_main_composes_customer_deployment_control_plane() -> None:
    assert (
        main.CUSTOMER_DEPLOYMENT_STORAGE_PATH
        == (
            TODOBA_CONTROL_PLANE_DATA_ROOT
            / "commercial"
            / "customer_deployments.json"
        )
    )

    assert (
        main.CUSTOMER_DEPLOYMENT_SECRET_STORAGE_PATH
        == (
            TODOBA_CONTROL_PLANE_DATA_ROOT
            / "commercial"
            / "customer_deployment_secrets.json"
        )
    )

    assert (
        main.TRUSTED_AGENT_ACCOUNT_BINDING_STORAGE_PATH
        == (
            TODOBA_CONTROL_PLANE_DATA_ROOT
            / "trading"
            / "trusted_agent_account_bindings.json"
        )
    )

    assert isinstance(
        main.customer_deployment_registry,
        CustomerDeploymentRegistry,
    )

    assert (
        main.customer_deployment_registry.storage_path
        == main.CUSTOMER_DEPLOYMENT_STORAGE_PATH
    )

    assert isinstance(
        main.customer_deployment_secret_store,
        CustomerDeploymentSecretStore,
    )

    assert (
        main.customer_deployment_secret_store.storage_path
        == main.CUSTOMER_DEPLOYMENT_SECRET_STORAGE_PATH
    )

    assert isinstance(
        main.trusted_agent_account_binding_store,
        TrustedAgentAccountBindingStore,
    )

    assert (
        main.trusted_agent_account_binding_store.storage_path
        == main.TRUSTED_AGENT_ACCOUNT_BINDING_STORAGE_PATH
    )

    assert isinstance(
        main.trusted_agent_account_binding_guard,
        TrustedAgentAccountBindingGuard,
    )

    assert (
        main.trusted_agent_account_binding_guard.store
        is main.trusted_agent_account_binding_store
    )

    assert isinstance(
        main.customer_deployment_runtime_projection,
        CustomerDeploymentRuntimeProjection,
    )

    assert (
        main.customer_deployment_runtime_projection._deployment_registry
        is main.customer_deployment_registry
    )

    assert (
        main.customer_deployment_runtime_projection._secret_store
        is main.customer_deployment_secret_store
    )

    assert (
        main.customer_deployment_runtime_projection._account_binding_store
        is main.trusted_agent_account_binding_store
    )


def test_main_composes_credentials_from_commercial_truth() -> None:
    assert isinstance(
        main.trusted_agent_credential_registry,
        TrustedAgentCredentialRegistry,
    )

    assert isinstance(
        main.trusted_agent_authenticator,
        TrustedAgentAuthenticator,
    )

    deployments = (
        main.customer_deployment_registry.all()
    )

    assert deployments

    for deployment in deployments:
        secrets = (
            main.customer_deployment_secret_store.get(
                deployment_id=(
                    deployment.deployment_id
                )
            )
        )

        assert secrets is not None

        assert (
            main.trusted_agent_credential_registry.get_secret(
                agent_id=deployment.agent_id
            )
            == secrets.agent_secret
        )

        assert main.trusted_agent_authenticator.authenticate(
            agent_id=deployment.agent_id,
            authorization=(
                f"Bearer {secrets.agent_secret}"
            ),
        )


def test_main_projects_execution_targets_from_commercial_truth() -> None:
    assert isinstance(
        main.execution_target_registry,
        ExecutionTargetRegistry,
    )

    deployments = (
        main.customer_deployment_registry.all()
    )

    assert (
        main.execution_target_registry.size()
        == len(deployments)
    )

    for deployment in deployments:
        account_fingerprint = (
            main.trusted_agent_account_binding_store
            .get_account_fingerprint(
                agent_id=deployment.agent_id
            )
        )

        assert account_fingerprint is not None

        target = (
            main.execution_target_registry.get(
                agent_id=deployment.agent_id
            )
        )

        assert target is not None

        assert (
            target.account_fingerprint
            == account_fingerprint
        )


def test_main_refresh_boundary_projects_commercial_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def project() -> int:
        calls.append(
            "project"
        )

        return 7

    monkeypatch.setattr(
        main.customer_deployment_runtime_projection,
        "project",
        project,
    )

    result = (
        main.refresh_customer_deployment_runtime_projection()
    )

    assert result == 7
    assert calls == ["project"]


def test_main_account_binding_check_uses_projected_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[
        tuple[str, str]
    ] = []

    targets = (
        ExecutionTarget(
            agent_id="trusted-agent-001",
            account_fingerprint="account-a",
        ),
        ExecutionTarget(
            agent_id="trusted-agent-002",
            account_fingerprint="account-b",
        ),
    )

    def all_targets() -> tuple[
        ExecutionTarget,
        ...,
    ]:
        return targets

    def require_binding(
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> str:
        calls.append(
            (
                agent_id,
                account_fingerprint,
            )
        )

        return account_fingerprint

    monkeypatch.setattr(
        main.execution_target_registry,
        "all",
        all_targets,
    )

    monkeypatch.setattr(
        main.trusted_agent_account_binding_guard,
        "require_binding",
        require_binding,
    )

    result = (
        main._require_trusted_agent_account_bindings()
    )

    assert result == (
        "account-a",
        "account-b",
    )

    assert calls == [
        (
            "trusted-agent-001",
            "account-a",
        ),
        (
            "trusted-agent-002",
            "account-b",
        ),
    ]


def test_main_account_binding_failure_stops_before_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def refresh_projection() -> int:
        calls.append(
            "projection"
        )

        return 1

    def require_account_bindings() -> tuple[
        str,
        ...,
    ]:
        calls.append(
            "account_bindings"
        )

        raise RuntimeError(
            "binding rejected"
        )

    def restore_records() -> int:
        calls.append(
            "records"
        )

        return 0

    monkeypatch.setattr(
        main,
        "refresh_customer_deployment_runtime_projection",
        refresh_projection,
        raising=False,
    )

    monkeypatch.setattr(
        main,
        "_require_trusted_agent_account_bindings",
        require_account_bindings,
        raising=False,
    )

    monkeypatch.setattr(
        main.execution_mission_record_recovery,
        "restore",
        restore_records,
    )

    async def run_lifespan() -> None:
        async with main.lifespan(
            main.app
        ):
            pass

    with pytest.raises(
        RuntimeError,
        match="binding rejected",
    ):
        asyncio.run(
            run_lifespan()
        )

    assert calls == [
        "projection",
        "account_bindings",
    ]
