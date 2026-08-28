"""
TODOBA Customer Deployment Package Build Worker Tests

Proof:
- missing immutable request fails closed
- already-published package bypasses bootstrap recovery
- request deployment mismatch fails closed
- bootstrap request mismatch fails closed
- bootstrap deployment mismatch fails closed
- busy deployment lock returns BUSY without building
- publication re-check under lock avoids duplicate build
- successful build requires authoritative publication
- build result identity mismatch fails closed
- missing post-build publication fails closed
- publication evidence mismatch fails closed
- build failure releases the deployment lock
- successful build returns only BUILT state

No real MetaEditor, HTTP, production state, or customer
credentials are used.
"""

from pathlib import Path

import pytest

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapPreparationResult,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
)
from backend.commercial.customer_deployment_package_build_worker import (
    CustomerDeploymentPackageBuildWorker,
    CustomerDeploymentPackageBuildWorkerStatus,
)
from backend.commercial.customer_deployment_package_publication import (
    CustomerDeploymentPublishedPackage,
)
from backend.commercial.customer_deployment_package_service import (
    CustomerDeploymentPackageResult,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
)


DEPLOYMENT_ID = "deployment-worker-001"
OTHER_DEPLOYMENT_ID = "deployment-worker-999"
BOOTSTRAP_REQUEST_ID = "bootstrap-worker-001"
AGENT_ID = "trusted-agent-worker-001"
ARTIFACT_SHA256 = "a" * 64
OTHER_SHA256 = "b" * 64


def make_request(
    *,
    deployment_id: str = DEPLOYMENT_ID,
    bootstrap_request_id: str = BOOTSTRAP_REQUEST_ID,
) -> CustomerDeploymentPackageBuildRequest:
    return CustomerDeploymentPackageBuildRequest(
        deployment_id=deployment_id,
        bootstrap_request_id=(
            bootstrap_request_id
        ),
    )


def make_prepared(
    *,
    enrollment_request_id: str = BOOTSTRAP_REQUEST_ID,
    deployment_id: str = DEPLOYMENT_ID,
    agent_id: str = AGENT_ID,
) -> CustomerDeploymentBootstrapPreparationResult:
    deployment = CustomerDeployment(
        customer_id="customer-worker-001",
        deployment_id=deployment_id,
        agent_id=agent_id,
    )

    secrets = CustomerDeploymentSecrets(
        deployment_id=deployment_id,
        agent_secret="worker-agent-secret",
        execution_mission_signing_secret=(
            "worker-execution-secret"
        ),
        control_mission_signing_secret=(
            "worker-control-secret"
        ),
    )

    return CustomerDeploymentBootstrapPreparationResult(
        enrollment_request_id=(
            enrollment_request_id
        ),
        deployment=deployment,
        secrets=secrets,
        account_fingerprint=(
            "broker-worker|login-worker|HEDGING"
        ),
    )


def make_package_result(
    tmp_path: Path,
    *,
    deployment_id: str = DEPLOYMENT_ID,
    agent_id: str = AGENT_ID,
    artifact_sha256: str = ARTIFACT_SHA256,
    artifact_size_bytes: int = 123,
) -> CustomerDeploymentPackageResult:
    return CustomerDeploymentPackageResult(
        deployment_id=deployment_id,
        agent_id=agent_id,
        artifact_path=(
            tmp_path
            / "TODOBA_Trusted_Agent.ex5"
        ),
        artifact_sha256=artifact_sha256,
        artifact_size_bytes=(
            artifact_size_bytes
        ),
    )


def make_publication(
    tmp_path: Path,
    *,
    deployment_id: str = DEPLOYMENT_ID,
    artifact_sha256: str = ARTIFACT_SHA256,
    artifact_size_bytes: int = 123,
    artifact_path: Path | None = None,
) -> CustomerDeploymentPublishedPackage:
    if artifact_path is None:
        artifact_path = (
            tmp_path
            / "TODOBA_Trusted_Agent.ex5"
        )

    return CustomerDeploymentPublishedPackage(
        deployment_id=deployment_id,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        artifact_size_bytes=(
            artifact_size_bytes
        ),
    )


class FakeBuildRequestStore:
    def __init__(
        self,
        request,
    ) -> None:
        self.request = request
        self.calls: list[str] = []

    def get(
        self,
        *,
        deployment_id: str,
    ):
        self.calls.append(
            deployment_id
        )

        return self.request


class FakeBootstrapService:
    def __init__(
        self,
        prepared=None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.prepared = prepared
        self.error = error
        self.calls: list[str] = []

    def recover_prepared_bootstrap(
        self,
        *,
        enrollment_request_id: str,
    ):
        self.calls.append(
            enrollment_request_id
        )

        if self.error is not None:
            raise self.error

        return self.prepared


class FakeBuildLock:
    def __init__(
        self,
    ) -> None:
        self.entered = False
        self.exited = False

    def __enter__(
        self,
    ):
        self.entered = True
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> bool:
        self.exited = True
        return False


class FakeBuildLockManager:
    def __init__(
        self,
        build_lock,
    ) -> None:
        self.build_lock = build_lock
        self.calls: list[str] = []

    def acquire(
        self,
        *,
        deployment_id: str,
    ):
        self.calls.append(
            deployment_id
        )

        return self.build_lock


class FakePublication:
    def __init__(
        self,
        responses,
    ) -> None:
        self.responses = list(
            responses
        )
        self.calls: list[str] = []

    def get_published_package(
        self,
        *,
        deployment_id: str,
    ):
        self.calls.append(
            deployment_id
        )

        if not self.responses:
            return None

        if len(self.responses) == 1:
            return self.responses[0]

        return self.responses.pop(
            0
        )


class FakePackageService:
    def __init__(
        self,
        result=None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = []

    def build_package(
        self,
        *,
        bootstrap_result,
    ):
        self.calls.append(
            bootstrap_result
        )

        if self.error is not None:
            raise self.error

        return self.result


def build_worker(
    *,
    request=None,
    prepared=None,
    build_lock=None,
    publication_responses=None,
    package_result=None,
    package_error: BaseException | None = None,
):
    if request is None:
        request = make_request()

    if prepared is None:
        prepared = make_prepared()

    if build_lock is None:
        build_lock = FakeBuildLock()

    if publication_responses is None:
        publication_responses = [
            None,
            None,
            None,
        ]

    request_store = FakeBuildRequestStore(
        request
    )

    bootstrap_service = FakeBootstrapService(
        prepared
    )

    lock_manager = FakeBuildLockManager(
        build_lock
    )

    publication = FakePublication(
        publication_responses
    )

    package_service = FakePackageService(
        package_result,
        error=package_error,
    )

    worker = CustomerDeploymentPackageBuildWorker(
        build_request_store=(
            request_store
        ),
        build_lock_manager=(
            lock_manager
        ),
        bootstrap_service=(
            bootstrap_service
        ),
        package_service=(
            package_service
        ),
        package_publication=(
            publication
        ),
    )

    return {
        "worker": worker,
        "request_store": request_store,
        "bootstrap_service": bootstrap_service,
        "lock_manager": lock_manager,
        "build_lock": build_lock,
        "publication": publication,
        "package_service": package_service,
    }


def test_missing_build_request_fails_closed(
    tmp_path: Path,
) -> None:
    context = build_worker(
        request=make_request()
    )

    context[
        "request_store"
    ].request = None

    with pytest.raises(
        RuntimeError,
        match="build request is missing",
    ):
        context[
            "worker"
        ].process(
            deployment_id=DEPLOYMENT_ID
        )

    assert context[
        "bootstrap_service"
    ].calls == []

    assert context[
        "lock_manager"
    ].calls == []

    assert context[
        "publication"
    ].calls == []

    assert context[
        "package_service"
    ].calls == []


def test_existing_publication_returns_already_ready_without_recovery(
    tmp_path: Path,
) -> None:
    published = make_publication(
        tmp_path
    )

    context = build_worker(
        publication_responses=[
            published
        ]
    )

    result = context[
        "worker"
    ].process(
        deployment_id=DEPLOYMENT_ID
    )

    assert (
        result.status
        == CustomerDeploymentPackageBuildWorkerStatus
        .ALREADY_READY
    )

    assert (
        result.deployment_id
        == DEPLOYMENT_ID
    )

    assert context[
        "bootstrap_service"
    ].calls == []

    assert context[
        "lock_manager"
    ].calls == []

    assert context[
        "package_service"
    ].calls == []


def test_request_deployment_identity_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    context = build_worker(
        request=make_request(
            deployment_id=(
                OTHER_DEPLOYMENT_ID
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="request deployment identity mismatch",
    ):
        context[
            "worker"
        ].process(
            deployment_id=DEPLOYMENT_ID
        )

    assert context[
        "publication"
    ].calls == []


def test_prepared_bootstrap_request_identity_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    context = build_worker(
        prepared=make_prepared(
            enrollment_request_id=(
                "bootstrap-wrong"
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="request identity",
    ):
        context[
            "worker"
        ].process(
            deployment_id=DEPLOYMENT_ID
        )

    assert context[
        "lock_manager"
    ].calls == []

    assert context[
        "package_service"
    ].calls == []


def test_prepared_bootstrap_deployment_identity_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    context = build_worker(
        prepared=make_prepared(
            deployment_id=(
                OTHER_DEPLOYMENT_ID
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="deployment identity",
    ):
        context[
            "worker"
        ].process(
            deployment_id=DEPLOYMENT_ID
        )

    assert context[
        "lock_manager"
    ].calls == []

    assert context[
        "package_service"
    ].calls == []


def test_busy_lock_returns_busy_without_build(
    tmp_path: Path,
) -> None:
    context = build_worker()

    context[
        "lock_manager"
    ].build_lock = None

    result = context[
        "worker"
    ].process(
        deployment_id=DEPLOYMENT_ID
    )

    assert (
        result.status
        == CustomerDeploymentPackageBuildWorkerStatus
        .BUSY
    )

    assert context[
        "bootstrap_service"
    ].calls == [
        BOOTSTRAP_REQUEST_ID
    ]

    assert context[
        "package_service"
    ].calls == []


def test_publication_recheck_under_lock_avoids_duplicate_build(
    tmp_path: Path,
) -> None:
    published = make_publication(
        tmp_path
    )

    context = build_worker(
        publication_responses=[
            None,
            published,
        ]
    )

    result = context[
        "worker"
    ].process(
        deployment_id=DEPLOYMENT_ID
    )

    assert (
        result.status
        == CustomerDeploymentPackageBuildWorkerStatus
        .ALREADY_READY
    )

    assert context[
        "build_lock"
    ].entered

    assert context[
        "build_lock"
    ].exited

    assert context[
        "package_service"
    ].calls == []


def test_successful_build_requires_and_matches_publication(
    tmp_path: Path,
) -> None:
    package_result = make_package_result(
        tmp_path
    )

    published = make_publication(
        tmp_path
    )

    context = build_worker(
        package_result=package_result,
        publication_responses=[
            None,
            None,
            published,
        ],
    )

    result = context[
        "worker"
    ].process(
        deployment_id=DEPLOYMENT_ID
    )

    assert (
        result.status
        == CustomerDeploymentPackageBuildWorkerStatus
        .BUILT
    )

    assert (
        context[
            "package_service"
        ].calls
        == [
            context[
                "bootstrap_service"
            ].prepared
        ]
    )

    assert context[
        "publication"
    ].calls == [
        DEPLOYMENT_ID,
        DEPLOYMENT_ID,
        DEPLOYMENT_ID,
    ]

    assert context[
        "build_lock"
    ].exited


def test_build_result_deployment_identity_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    package_result = make_package_result(
        tmp_path,
        deployment_id=(
            OTHER_DEPLOYMENT_ID
        ),
    )

    context = build_worker(
        package_result=package_result
    )

    with pytest.raises(
        RuntimeError,
        match="Built package deployment identity mismatch",
    ):
        context[
            "worker"
        ].process(
            deployment_id=DEPLOYMENT_ID
        )

    assert context[
        "build_lock"
    ].exited


def test_build_result_agent_identity_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    package_result = make_package_result(
        tmp_path,
        agent_id="trusted-agent-wrong",
    )

    context = build_worker(
        package_result=package_result
    )

    with pytest.raises(
        RuntimeError,
        match="Built package agent identity mismatch",
    ):
        context[
            "worker"
        ].process(
            deployment_id=DEPLOYMENT_ID
        )

    assert context[
        "build_lock"
    ].exited


def test_build_without_post_build_publication_fails_closed(
    tmp_path: Path,
) -> None:
    package_result = make_package_result(
        tmp_path
    )

    context = build_worker(
        package_result=package_result,
        publication_responses=[
            None,
            None,
            None,
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="without authoritative publication",
    ):
        context[
            "worker"
        ].process(
            deployment_id=DEPLOYMENT_ID
        )

    assert context[
        "build_lock"
    ].exited


def test_publication_evidence_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    package_result = make_package_result(
        tmp_path
    )

    published = make_publication(
        tmp_path,
        artifact_sha256=(
            OTHER_SHA256
        ),
    )

    context = build_worker(
        package_result=package_result,
        publication_responses=[
            None,
            None,
            published,
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="artifact hash mismatch",
    ):
        context[
            "worker"
        ].process(
            deployment_id=DEPLOYMENT_ID
        )

    assert context[
        "build_lock"
    ].exited


def test_build_failure_releases_lock(
    tmp_path: Path,
) -> None:
    context = build_worker(
        package_error=RuntimeError(
            "simulated-build-failure"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="simulated-build-failure",
    ):
        context[
            "worker"
        ].process(
            deployment_id=DEPLOYMENT_ID
        )

    assert context[
        "build_lock"
    ].entered

    assert context[
        "build_lock"
    ].exited


def test_result_status_surface_is_closed() -> None:
    assert {
        status.value
        for status
        in CustomerDeploymentPackageBuildWorkerStatus
    } == {
        "BUILT",
        "ALREADY_READY",
        "BUSY",
    }
