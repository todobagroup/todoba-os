"""
TODOBA Test Configuration

Provides deterministic non-production environment values
and isolated persistence for application-level tests.

Production customer fleet configuration must never leak
from the repository .env file into the pytest runtime.
"""

import os
from collections.abc import Iterator
from pathlib import Path


_TEST_ENVIRONMENT = {
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

from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)


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