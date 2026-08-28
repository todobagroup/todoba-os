"""
TODOBA Customer Deployment Package Build Request Store Tests

Proof:
- missing durable storage is fail-closed
- explicit initialization creates an empty ready store
- immutable request survives restart
- identical retry across independent store instances converges
- conflicting deployment reuse fails closed
- independent instances cannot overwrite one deployment request
- persisted request contains only allowed non-secret identity
- abandoned staging state is not authoritative
- unexpected storage material fails closed
- directory identity must match deployment identity
- implementation uses no-overwrite atomic directory rename

All persistence is isolated beneath pytest tmp_path.
"""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
    CustomerDeploymentPackageBuildRequestStore,
)


def make_request(
    *,
    deployment_id: str = "deployment-build-001",
    bootstrap_request_id: str = "bootstrap-request-001",
) -> CustomerDeploymentPackageBuildRequest:
    return CustomerDeploymentPackageBuildRequest(
        deployment_id=deployment_id,
        bootstrap_request_id=(
            bootstrap_request_id
        ),
    )


def request_files(
    root: Path,
) -> tuple[
    Path,
    ...,
]:
    return tuple(
        root.glob(
            "build-request-*/request.json"
        )
    )


def test_store_requires_path() -> None:
    with pytest.raises(
        TypeError,
        match="storage_root must be Path",
    ):
        CustomerDeploymentPackageBuildRequestStore(
            "not-a-path"
        )


def test_missing_store_requires_explicit_initialization(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "package_build_requests"
    )

    store = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )

    assert not store.is_ready()
    assert not root.exists()

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.get(
            deployment_id="deployment-build-001"
        )

    with pytest.raises(
        RuntimeError,
        match="not initialized",
    ):
        store.register(
            make_request()
        )

    store.initialize_empty()

    assert store.is_ready()
    assert root.is_dir()
    assert store.size() == 0

    # A second independently constructed instance must
    # recognize the already-initialized durable root.
    second = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )

    assert second.is_ready()
    assert second.size() == 0


def test_registered_request_survives_restart(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "package_build_requests"
    )

    store = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )
    store.initialize_empty()

    request = make_request()

    registered = store.register(
        request
    )

    assert registered == request
    assert store.size() == 1

    restarted = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )

    assert restarted.is_ready()

    assert (
        restarted.get(
            deployment_id=(
                request.deployment_id
            )
        )
        == request
    )

    assert restarted.all() == (
        request,
    )


def test_identical_retry_across_independent_instances_is_idempotent(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "package_build_requests"
    )

    first = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )
    first.initialize_empty()

    second = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )

    request = make_request()

    assert first.register(
        request
    ) == request

    paths = request_files(
        root
    )

    assert len(paths) == 1

    bytes_before = paths[
        0
    ].read_bytes()

    assert second.register(
        request
    ) == request

    paths_after = request_files(
        root
    )

    assert len(paths_after) == 1

    assert (
        paths_after[
            0
        ].read_bytes()
        == bytes_before
    )


def test_conflicting_retry_same_deployment_fails_closed_across_instances(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "package_build_requests"
    )

    first = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )
    first.initialize_empty()

    second = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )

    original = make_request(
        bootstrap_request_id=(
            "bootstrap-request-original"
        )
    )

    conflicting = make_request(
        bootstrap_request_id=(
            "bootstrap-request-conflicting"
        )
    )

    first.register(
        original
    )

    with pytest.raises(
        ValueError,
        match=(
            "different bootstrap request"
        ),
    ):
        second.register(
            conflicting
        )

    assert (
        first.get(
            deployment_id=(
                original.deployment_id
            )
        )
        == original
    )

    assert len(
        request_files(
            root
        )
    ) == 1


def test_independent_instances_cannot_overwrite_same_deployment_request(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "package_build_requests"
    )

    initializer = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )
    initializer.initialize_empty()

    first = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )

    second = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )

    request_a = make_request(
        bootstrap_request_id="bootstrap-a"
    )

    request_b = make_request(
        bootstrap_request_id="bootstrap-b"
    )

    def attempt(
        store,
        request,
    ):
        try:
            result = store.register(
                request
            )

            return (
                "ok",
                result.bootstrap_request_id,
            )
        except ValueError:
            return (
                "conflict",
                request.bootstrap_request_id,
            )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = (
            executor.submit(
                attempt,
                first,
                request_a,
            ),
            executor.submit(
                attempt,
                second,
                request_b,
            ),
        )

        outcomes = tuple(
            future.result()
            for future in futures
        )

    assert sorted(
        outcome[
            0
        ]
        for outcome in outcomes
    ) == [
        "conflict",
        "ok",
    ]

    winner = next(
        outcome[
            1
        ]
        for outcome in outcomes
        if outcome[
            0
        ]
        == "ok"
    )

    recovered = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        ).get(
            deployment_id=(
                request_a.deployment_id
            )
        )
    )

    assert recovered is not None

    assert (
        recovered.bootstrap_request_id
        == winner
    )

    assert len(
        request_files(
            root
        )
    ) == 1


def test_persisted_request_contains_only_allowed_non_secret_identity(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "package_build_requests"
    )

    store = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )
    store.initialize_empty()

    request = make_request()

    store.register(
        request
    )

    paths = request_files(
        root
    )

    assert len(paths) == 1

    payload = json.loads(
        paths[
            0
        ].read_text(
            encoding="utf-8"
        )
    )

    assert set(
        payload
    ) == {
        "version",
        "deployment_id",
        "bootstrap_request_id",
    }

    assert (
        payload[
            "deployment_id"
        ]
        == request.deployment_id
    )

    assert (
        payload[
            "bootstrap_request_id"
        ]
        == request.bootstrap_request_id
    )

    persisted_text = paths[
        0
    ].read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "customer_id",
        "account_fingerprint",
        "agent_secret",
        "execution_mission_signing_secret",
        "control_mission_signing_secret",
        "artifact_sha256",
        "artifact_size_bytes",
        "status",
        "worker_id",
    ):
        assert forbidden not in persisted_text


def test_abandoned_staging_directory_is_not_authoritative(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "package_build_requests"
    )

    store = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )
    store.initialize_empty()

    abandoned = (
        root
        / ".staging-abandoned"
    )

    abandoned.mkdir()

    (
        abandoned
        / "partial-data"
    ).write_text(
        "incomplete",
        encoding="utf-8",
    )

    restarted = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )

    assert restarted.is_ready()
    assert restarted.size() == 0
    assert restarted.all() == ()


def test_unexpected_storage_material_fails_closed(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "package_build_requests"
    )

    store = (
        CustomerDeploymentPackageBuildRequestStore(
            root
        )
    )
    store.initialize_empty()

    (
        root
        / "unexpected.txt"
    ).write_text(
        "unsafe",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected material",
    ):
        CustomerDeploymentPackageBuildRequestStore(
            root
        )


def test_request_directory_identity_must_match_deployment_identity(
    tmp_path: Path,
) -> None:
    root = (
        tmp_path
        / "package_build_requests"
    )

    root.mkdir()

    wrong_directory = (
        root
        / (
            "build-request-"
            + (
                "0"
                * 64
            )
        )
    )

    wrong_directory.mkdir()

    (
        wrong_directory
        / "request.json"
    ).write_text(
        json.dumps(
            {
                "version": 1,
                "deployment_id": (
                    "deployment-real"
                ),
                "bootstrap_request_id": (
                    "bootstrap-real"
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=(
            "directory identity does not match"
        ),
    ):
        CustomerDeploymentPackageBuildRequestStore(
            root
        )


def test_owner_uses_atomic_no_overwrite_directory_publish() -> None:
    import ast

    source = (
        Path(
            "backend/commercial/"
            "customer_deployment_package_build_request_store.py"
        )
        .read_text(
            encoding="utf-8"
        )
    )

    tree = ast.parse(
        source
    )

    os_calls = {
        node.func.attr
        for node in ast.walk(
            tree
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and isinstance(
                node.func.value,
                ast.Name,
            )
            and node.func.value.id == "os"
        )
    }

    assert "rename" in os_calls
    assert "replace" not in os_calls

    assert "filelock" not in source.lower()
    assert "portalocker" not in source.lower()

    assert (
        "CustomerDeploymentSecrets"
        not in source
    )

    assert (
        "account_fingerprint"
        not in source
    )
