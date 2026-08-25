"""
TODOBA Test Configuration

Provides deterministic non-production environment values
and isolated persistence for application-level tests.

Production customer fleet configuration must never leak
from the repository .env file into the pytest runtime.
"""

import base64
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path


_TEST_CONTROL_PLANE_DIRECTORY = (
    tempfile.TemporaryDirectory(
        prefix="todoba-pytest-control-plane-"
    )
)

_TEST_CONTROL_PLANE_DATA_ROOT = Path(
    _TEST_CONTROL_PLANE_DIRECTORY.name
)

_TEST_CUSTOMER_DEPLOYMENT_MASTER_KEY_BYTES = (
    bytes(range(32))
)

_TEST_CUSTOMER_DEPLOYMENT_MASTER_KEY = (
    base64.urlsafe_b64encode(
        _TEST_CUSTOMER_DEPLOYMENT_MASTER_KEY_BYTES
    ).decode("ascii")
)


_TEST_ENVIRONMENT = {
    "TODOBA_CONTROL_PLANE_DATA_ROOT": str(
        _TEST_CONTROL_PLANE_DATA_ROOT
    ),
    "TODOBA_CUSTOMER_PACKAGE_ROOT": str(
        _TEST_CONTROL_PLANE_DATA_ROOT
        / "customer-packages"
    ),
    "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY": (
        _TEST_CUSTOMER_DEPLOYMENT_MASTER_KEY
    ),
    "TODOBA_TRUSTED_AGENT_ID": (
        "trusted-agent-001"
    ),
    "TODOBA_TRUSTED_AGENT_SECRET": (
        "test-trusted-agent-secret"
    ),
    "TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT": (
        "test-account"
    ),
    "TODOBA_EXECUTION_MISSION_SIGNING_SECRET": (
        "test-execution-mission-signing-secret"
    ),
    "TODOBA_CONTROL_MISSION_SIGNING_SECRET": (
        "test-control-mission-signing-secret"
    ),
    "TODOBA_TRUSTED_AGENTS_JSON": "",
    "TODOBA_EXECUTION_TARGETS_JSON": "",
}


for environment_name, environment_value in (
    _TEST_ENVIRONMENT.items()
):
    os.environ[
        environment_name
    ] = environment_value


import pytest

from backend.commercial.customer_access_credential_registry import (
    CustomerAccessCredentialRegistry,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
    CustomerDeploymentSecretStore,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


def _initialize_test_control_plane() -> None:
    deployment_registry = (
        CustomerDeploymentRegistry(
            _TEST_CONTROL_PLANE_DATA_ROOT
            / "commercial"
            / "customer_deployments.json"
        )
    )

    deployment_registry.initialize_empty()

    deployment_registry.register(
        CustomerDeployment(
            customer_id="test-customer-001",
            deployment_id="test-deployment-001",
            agent_id="trusted-agent-001",
        )
    )

    customer_identity_registry = (
        CustomerIdentityRegistry(
            _TEST_CONTROL_PLANE_DATA_ROOT
            / "commercial"
            / "customer_identities.json"
        )
    )

    customer_identity_registry.initialize_empty()

    customer_identity_registry.register(
        CustomerIdentity(
            customer_id="test-customer-001"
        )
    )

    customer_access_credential_registry = (
        CustomerAccessCredentialRegistry(
            _TEST_CONTROL_PLANE_DATA_ROOT
            / "commercial"
            / "customer_access_credentials.json",
            customer_identity_registry=(
                customer_identity_registry
            ),
        )
    )

    customer_access_credential_registry.initialize_empty()

    customer_deployment_entitlement_registry = (
        CustomerDeploymentEntitlementRegistry(
            _TEST_CONTROL_PLANE_DATA_ROOT
            / "commercial"
            / "customer_deployment_entitlements.json",
            deployment_registry=(
                deployment_registry
            ),
        )
    )

    customer_deployment_entitlement_registry.initialize_empty()

    secret_store = (
        CustomerDeploymentSecretStore(
            _TEST_CONTROL_PLANE_DATA_ROOT
            / "commercial"
            / "customer_deployment_secrets.json",
            master_key=(
                _TEST_CUSTOMER_DEPLOYMENT_MASTER_KEY_BYTES
            ),
        )
    )

    secret_store.initialize_empty()

    secret_store.register(
        CustomerDeploymentSecrets(
            deployment_id="test-deployment-001",
            agent_secret=(
                "test-trusted-agent-secret"
            ),
            execution_mission_signing_secret=(
                "test-execution-mission-signing-secret"
            ),
            control_mission_signing_secret=(
                "test-control-mission-signing-secret"
            ),
        )
    )

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            _TEST_CONTROL_PLANE_DATA_ROOT
            / "trading"
            / "trusted_agent_account_bindings.json"
        )
    )

    account_binding_store.initialize_empty()

    account_binding_store.bind(
        agent_id="trusted-agent-001",
        account_fingerprint="test-account",
    )


_initialize_test_control_plane()


@pytest.fixture
def commercial_executor_fleet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Prepare isolated durable commercial routing truth
    for REMOTE_VPS Executor tests.

    This fixture intentionally does not create or expose
    customer deployment secret material.
    """

    data_root = (
        tmp_path
        / "commercial-executor-control-plane"
    )

    def prepare(
        targets: tuple[
            tuple[str, str],
            ...,
        ],
    ) -> Path:
        if not targets:
            raise ValueError(
                "commercial Executor fleet "
                "must contain at least one target."
            )

        monkeypatch.setenv(
            "TODOBA_CONTROL_PLANE_DATA_ROOT",
            str(data_root),
        )

        monkeypatch.setenv(
            "TODOBA_TRUSTED_AGENT_ID",
            "",
        )

        monkeypatch.setenv(
            "TODOBA_TRUSTED_AGENTS_JSON",
            "",
        )

        monkeypatch.setenv(
            "TODOBA_EXECUTION_TARGETS_JSON",
            "",
        )

        deployment_registry = (
            CustomerDeploymentRegistry(
                data_root
                / "commercial"
                / "customer_deployments.json"
            )
        )

        if not deployment_registry.is_ready():
            deployment_registry.initialize_empty()

        account_binding_store = (
            TrustedAgentAccountBindingStore(
                data_root
                / "trading"
                / (
                    "trusted_agent_"
                    "account_bindings.json"
                )
            )
        )

        if not account_binding_store.is_ready():
            account_binding_store.initialize_empty()

        seen_agent_ids: set[str] = set()

        for index, (
            agent_id,
            account_fingerprint,
        ) in enumerate(
            targets,
            start=1,
        ):
            if agent_id in seen_agent_ids:
                raise ValueError(
                    "commercial Executor fleet "
                    "contains duplicate agent_id."
                )

            seen_agent_ids.add(
                agent_id
            )

            deployment_registry.register(
                CustomerDeployment(
                    customer_id=(
                        "executor-test-customer-"
                        f"{index:03d}"
                    ),
                    deployment_id=(
                        "executor-test-deployment-"
                        f"{index:03d}"
                    ),
                    agent_id=agent_id,
                )
            )

            account_binding_store.bind(
                agent_id=agent_id,
                account_fingerprint=(
                    account_fingerprint
                ),
            )

        return data_root

    return prepare


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int,
) -> None:
    del session
    del exitstatus

    _TEST_CONTROL_PLANE_DIRECTORY.cleanup()


@pytest.fixture
def isolated_main_execution_mission_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    from backend import main

    stores = (
        main.execution_mission_acknowledgement_store,
        main.execution_mission_execution_started_store,
        main.execution_mission_completed_store,
        main.execution_mission_failed_store,
        main.broker_execution_evidence_store,
    )

    def drain_stores() -> None:
        for store in stores:
            while store.pop() is not None:
                pass

    def drain_mission_registry() -> None:
        for record in (
            main.execution_mission_registry.list()
        ):
            main.execution_mission_registry.remove(
                record.mission.mission_id
            )

    drain_stores()
    drain_mission_registry()

    storage_path = (
        tmp_path
        / "execution_mission_evidence.json"
    )

    isolated_persistence = (
        ExecutionMissionEvidencePersistence(
            storage_path
        )
    )

    original_save = (
        ExecutionMissionEvidencePersistence.save
    )

    original_remove = (
        ExecutionMissionEvidencePersistence.remove
    )

    def save_isolated(
        persistence: ExecutionMissionEvidencePersistence,
        evidence: object,
    ) -> None:
        original_save(
            isolated_persistence,
            evidence,
        )

    def remove_isolated(
        persistence: ExecutionMissionEvidencePersistence,
        evidence: object,
    ) -> bool:
        return original_remove(
            isolated_persistence,
            evidence,
        )

    monkeypatch.setattr(
        ExecutionMissionEvidencePersistence,
        "save",
        save_isolated,
    )

    monkeypatch.setattr(
        ExecutionMissionEvidencePersistence,
        "remove",
        remove_isolated,
    )

    yield storage_path

    drain_stores()
    drain_mission_registry()