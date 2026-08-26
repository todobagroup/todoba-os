"""
TODOBA Customer Deployment Package Service Tests

Proof:
- one customer-safe EX5 is published
- prepared bootstrap builds before deployment activation
- published metadata matches the real artifact
- repeated build atomically replaces the artifact
- failed rebuild preserves the previously published EX5
- temporary provisioning/build material is always cleaned
- unexpected customer package material fails closed
- empty EX5 fails closed
- unexpected builder artifact path fails closed
- package/workspace roots cannot overlap protected roots
- published package lookup rejects unsafe package contents

All persistence and artifacts are isolated beneath tmp_path.
No real MetaEditor or production data is used.
"""

from pathlib import Path
import hashlib

import pytest

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapPreparationResult,
    CustomerDeploymentBootstrapResult,
)
from backend.commercial.customer_deployment_package_service import (
    CustomerDeploymentPackageService,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
)


ARTIFACT_NAME = "TODOBA_Trusted_Agent.ex5"


def make_bootstrap_result(
    *,
    deployment_id: str = "deployment-package-001",
    agent_id: str = "trusted-agent-package-001",
) -> CustomerDeploymentBootstrapResult:
    deployment = CustomerDeployment(
        customer_id="customer-package-001",
        deployment_id=deployment_id,
        agent_id=agent_id,
    )

    secrets = CustomerDeploymentSecrets(
        deployment_id=deployment_id,
        agent_secret="package-agent-secret",
        execution_mission_signing_secret=(
            "package-execution-secret"
        ),
        control_mission_signing_secret=(
            "package-control-secret"
        ),
    )

    return CustomerDeploymentBootstrapResult(
        enrollment_request_id="request-package-001",
        deployment=deployment,
        secrets=secrets,
        account_fingerprint="broker:account-package-001",
        projected_deployment_count=1,
    )


def make_bootstrap_preparation_result(
    *,
    deployment_id: str = "deployment-package-prepared-001",
    agent_id: str = "trusted-agent-package-prepared-001",
) -> CustomerDeploymentBootstrapPreparationResult:
    complete = make_bootstrap_result(
        deployment_id=deployment_id,
        agent_id=agent_id,
    )

    return CustomerDeploymentBootstrapPreparationResult(
        enrollment_request_id=(
            complete.enrollment_request_id
        ),
        deployment=complete.deployment,
        secrets=complete.secrets,
        account_fingerprint=(
            complete.account_fingerprint
        ),
    )

def prepare_roots(
    tmp_path: Path,
) -> dict[str, Path]:
    repository_root = (
        tmp_path
        / "repository"
    )

    source_root = (
        repository_root
        / "MQL5"
    )

    source_root.mkdir(
        parents=True
    )

    platform_root = (
        tmp_path
        / "platform"
        / "MQL5"
    )

    platform_root.mkdir(
        parents=True
    )

    workspace_root = (
        tmp_path
        / "workspace"
    )

    package_root = (
        tmp_path
        / "packages"
    )

    return {
        "repository_root": repository_root,
        "source_root": source_root,
        "platform_root": platform_root,
        "workspace_root": workspace_root,
        "package_root": package_root,
    }


def package_directory(
    *,
    package_root: Path,
    deployment_id: str,
) -> Path:
    digest = hashlib.sha256(
        deployment_id.encode(
            "utf-8"
        )
    ).hexdigest()

    return (
        package_root
        / f"customer-deployment-{digest}"
    )


def make_provisioner():
    def provisioner(
        *,
        mql5_source_root: Path,
        output_root: Path,
        agent_id: str,
        account_fingerprint: str,
        agent_secret: str,
        execution_mission_signing_secret: str,
        control_mission_signing_secret: str,
    ) -> Path:
        assert mql5_source_root.is_dir()

        deployment_root = (
            output_root
            / agent_id
        )

        credential_root = (
            deployment_root
            / "MQL5"
            / "Include"
            / "TODOBAExecution"
        )

        credential_root.mkdir(
            parents=True
        )

        (
            credential_root
            / "TODOBAAgentCredentials.mqh"
        ).write_text(
            (
                f"{account_fingerprint}\n"
                f"{agent_secret}\n"
                f"{execution_mission_signing_secret}\n"
                f"{control_mission_signing_secret}\n"
            ),
            encoding="utf-8",
        )

        agent_root = (
            deployment_root
            / "MQL5"
            / "Experts"
            / "TODOBA"
        )

        agent_root.mkdir(
            parents=True
        )

        (
            agent_root
            / "TODOBA_Trusted_Agent.mq5"
        ).write_text(
            "// isolated package test source\n",
            encoding="utf-8",
        )

        return deployment_root

    return provisioner


def make_builder(
    *,
    artifact_bytes_getter,
    fail_getter=lambda: False,
):
    def builder(
        *,
        deployment_root: Path,
        platform_mql5_root: Path,
        build_root: Path,
        compiler_runner,
    ) -> Path:
        assert platform_mql5_root.is_dir()
        assert callable(
            compiler_runner
        )

        build_root.mkdir(
            parents=True
        )

        (
            build_root
            / "compile.log"
        ).write_text(
            "isolated package build log\n",
            encoding="utf-8",
        )

        if fail_getter():
            raise RuntimeError(
                "simulated secure build failure"
            )

        artifact_directory = (
            deployment_root
            / "artifact"
        )

        artifact_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        artifact_path = (
            artifact_directory
            / ARTIFACT_NAME
        )

        artifact_path.write_bytes(
            artifact_bytes_getter()
        )

        source_tree = (
            deployment_root
            / "MQL5"
        )

        if source_tree.exists():
            import shutil

            shutil.rmtree(
                source_tree
            )

        if build_root.exists():
            import shutil

            shutil.rmtree(
                build_root
            )

        return artifact_path

    return builder


def compiler_runner(
    *,
    agent_path: Path,
    mql5_root: Path,
    log_path: Path,
) -> int:
    raise AssertionError(
        "Injected fake builder should not call "
        "the compiler runner."
    )


def build_service(
    tmp_path: Path,
    *,
    artifact_bytes_getter=lambda: (
        b"TODOBA-PACKAGE-ARTIFACT-V1"
    ),
    fail_getter=lambda: False,
):
    roots = prepare_roots(
        tmp_path
    )

    service = (
        CustomerDeploymentPackageService(
            mql5_source_root=(
                roots["source_root"]
            ),
            platform_mql5_root=(
                roots["platform_root"]
            ),
            workspace_root=(
                roots["workspace_root"]
            ),
            package_root=(
                roots["package_root"]
            ),
            compiler_runner=compiler_runner,
            provisioner=make_provisioner(),
            builder=make_builder(
                artifact_bytes_getter=(
                    artifact_bytes_getter
                ),
                fail_getter=fail_getter,
            ),
        )
    )

    return service, roots


def test_prepared_bootstrap_builds_without_deployment_activation(
    tmp_path: Path,
) -> None:
    artifact_bytes = (
        b"TODOBA-PREPARED-CUSTOMER-EX5"
    )

    service, _ = build_service(
        tmp_path,
        artifact_bytes_getter=(
            lambda: artifact_bytes
        ),
    )

    deployment_registry = (
        CustomerDeploymentRegistry(
            tmp_path
            / "customer_deployments.json"
        )
    )
    deployment_registry.initialize_empty()

    prepared = (
        make_bootstrap_preparation_result()
    )

    assert deployment_registry.size() == 0

    result = service.build_package(
        bootstrap_result=prepared
    )

    assert result.artifact_path.is_file()

    assert (
        result.artifact_path.read_bytes()
        == artifact_bytes
    )

    assert (
        result.deployment_id
        == prepared.deployment.deployment_id
    )

    assert (
        result.agent_id
        == prepared.deployment.agent_id
    )

    # Package build must not cross the commercial
    # deployment activation barrier.
    assert deployment_registry.size() == 0

def test_build_publishes_exactly_one_customer_safe_ex5(
    tmp_path: Path,
) -> None:
    artifact_bytes = (
        b"TODOBA-CUSTOMER-EX5"
    )

    service, roots = build_service(
        tmp_path,
        artifact_bytes_getter=(
            lambda: artifact_bytes
        ),
    )

    bootstrap_result = (
        make_bootstrap_result()
    )

    result = service.build_package(
        bootstrap_result=bootstrap_result
    )

    assert result.artifact_path.is_file()

    assert (
        result.artifact_path.read_bytes()
        == artifact_bytes
    )

    assert (
        tuple(
            result.artifact_path
            .parent
            .iterdir()
        )
        == (
            result.artifact_path,
        )
    )

    assert not list(
        roots[
            "package_root"
        ].rglob(
            "*.mq5"
        )
    )

    assert not list(
        roots[
            "package_root"
        ].rglob(
            "*.mqh"
        )
    )

    assert not list(
        roots[
            "package_root"
        ].rglob(
            "*.log"
        )
    )

    assert (
        roots[
            "workspace_root"
        ].is_dir()
    )

    assert not list(
        roots[
            "workspace_root"
        ].iterdir()
    )


def test_published_metadata_matches_real_artifact(
    tmp_path: Path,
) -> None:
    artifact_bytes = (
        b"TODOBA-METADATA-PROOF"
    )

    service, _ = build_service(
        tmp_path,
        artifact_bytes_getter=(
            lambda: artifact_bytes
        ),
    )

    bootstrap_result = (
        make_bootstrap_result()
    )

    result = service.build_package(
        bootstrap_result=bootstrap_result
    )

    expected_hash = hashlib.sha256(
        artifact_bytes
    ).hexdigest()

    assert (
        result.deployment_id
        == bootstrap_result
        .deployment
        .deployment_id
    )

    assert (
        result.agent_id
        == bootstrap_result
        .deployment
        .agent_id
    )

    assert (
        result.artifact_sha256
        == expected_hash
    )

    assert (
        result.artifact_size_bytes
        == len(
            artifact_bytes
        )
    )

    restored = (
        service.get_published_package(
            deployment_id=(
                result.deployment_id
            ),
            agent_id=result.agent_id,
        )
    )

    assert restored is not None

    assert (
        restored.artifact_sha256
        == expected_hash
    )

    assert (
        restored.artifact_size_bytes
        == len(
            artifact_bytes
        )
    )


def test_rebuild_atomically_replaces_existing_package(
    tmp_path: Path,
) -> None:
    state = {
        "artifact": b"TODOBA-V1",
    }

    service, roots = build_service(
        tmp_path,
        artifact_bytes_getter=(
            lambda: state[
                "artifact"
            ]
        ),
    )

    bootstrap_result = (
        make_bootstrap_result()
    )

    first = service.build_package(
        bootstrap_result=bootstrap_result
    )

    first_path = (
        first.artifact_path
    )

    assert (
        first_path.read_bytes()
        == b"TODOBA-V1"
    )

    state[
        "artifact"
    ] = b"TODOBA-V2"

    second = service.build_package(
        bootstrap_result=bootstrap_result
    )

    assert (
        second.artifact_path
        == first_path
    )

    assert (
        second.artifact_path
        .read_bytes()
        == b"TODOBA-V2"
    )

    assert (
        second.artifact_sha256
        != first.artifact_sha256
    )

    staging_root = (
        roots[
            "package_root"
        ]
        / ".staging"
    )

    if staging_root.exists():
        assert not list(
            staging_root.iterdir()
        )


def test_failed_rebuild_preserves_existing_published_ex5(
    tmp_path: Path,
) -> None:
    state = {
        "artifact": b"TODOBA-STABLE",
        "fail": False,
    }

    service, roots = build_service(
        tmp_path,
        artifact_bytes_getter=(
            lambda: state[
                "artifact"
            ]
        ),
        fail_getter=(
            lambda: state[
                "fail"
            ]
        ),
    )

    bootstrap_result = (
        make_bootstrap_result()
    )

    original = service.build_package(
        bootstrap_result=bootstrap_result
    )

    original_path = (
        original.artifact_path
    )

    original_hash = (
        original.artifact_sha256
    )

    state[
        "artifact"
    ] = b"TODOBA-FAILED-REBUILD"

    state[
        "fail"
    ] = True

    with pytest.raises(
        RuntimeError,
        match="simulated secure build failure",
    ):
        service.build_package(
            bootstrap_result=(
                bootstrap_result
            )
        )

    assert original_path.is_file()

    assert (
        original_path.read_bytes()
        == b"TODOBA-STABLE"
    )

    assert (
        hashlib.sha256(
            original_path.read_bytes()
        ).hexdigest()
        == original_hash
    )

    assert not list(
        roots[
            "workspace_root"
        ].iterdir()
    )

    staging_root = (
        roots[
            "package_root"
        ]
        / ".staging"
    )

    if staging_root.exists():
        assert not list(
            staging_root.iterdir()
        )


def test_unexpected_existing_customer_package_material_fails_closed(
    tmp_path: Path,
) -> None:
    service, roots = build_service(
        tmp_path
    )

    bootstrap_result = (
        make_bootstrap_result()
    )

    directory = package_directory(
        package_root=(
            roots[
                "package_root"
            ]
        ),
        deployment_id=(
            bootstrap_result
            .deployment
            .deployment_id
        ),
    )

    directory.mkdir(
        parents=True
    )

    (
        directory
        / "unexpected-secret.txt"
    ).write_text(
        "must never be accepted\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected material",
    ):
        service.build_package(
            bootstrap_result=(
                bootstrap_result
            )
        )

    assert (
        directory
        / "unexpected-secret.txt"
    ).is_file()

    assert not roots[
        "workspace_root"
    ].exists()


def test_empty_built_ex5_fails_closed_and_cleans_workspace(
    tmp_path: Path,
) -> None:
    service, roots = build_service(
        tmp_path,
        artifact_bytes_getter=lambda: b"",
    )

    with pytest.raises(
        RuntimeError,
        match="artifact is empty",
    ):
        service.build_package(
            bootstrap_result=(
                make_bootstrap_result()
            )
        )

    assert roots[
        "workspace_root"
    ].is_dir()

    assert not list(
        roots[
            "workspace_root"
        ].iterdir()
    )

    package_root = roots[
        "package_root"
    ]

    if package_root.exists():
        assert not list(
            package_root.glob(
                "customer-deployment-*"
            )
        )


def test_unexpected_builder_artifact_path_fails_closed(
    tmp_path: Path,
) -> None:
    roots = prepare_roots(
        tmp_path
    )

    def wrong_builder(
        *,
        deployment_root: Path,
        platform_mql5_root: Path,
        build_root: Path,
        compiler_runner,
    ) -> Path:
        import shutil

        wrong_directory = (
            deployment_root
            / "wrong"
        )

        wrong_directory.mkdir(
            parents=True
        )

        wrong_artifact = (
            wrong_directory
            / ARTIFACT_NAME
        )

        wrong_artifact.write_bytes(
            b"WRONG-PATH-EX5"
        )

        source_tree = (
            deployment_root
            / "MQL5"
        )

        if source_tree.exists():
            shutil.rmtree(
                source_tree
            )

        return wrong_artifact

    service = CustomerDeploymentPackageService(
        mql5_source_root=(
            roots[
                "source_root"
            ]
        ),
        platform_mql5_root=(
            roots[
                "platform_root"
            ]
        ),
        workspace_root=(
            roots[
                "workspace_root"
            ]
        ),
        package_root=(
            roots[
                "package_root"
            ]
        ),
        compiler_runner=compiler_runner,
        provisioner=make_provisioner(),
        builder=wrong_builder,
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected artifact path",
    ):
        service.build_package(
            bootstrap_result=(
                make_bootstrap_result()
            )
        )

    assert not list(
        roots[
            "workspace_root"
        ].iterdir()
    )


@pytest.mark.parametrize(
    (
        "workspace_selector",
        "package_selector",
    ),
    (
        (
            "inside_repository",
            "normal",
        ),
        (
            "normal",
            "inside_repository",
        ),
        (
            "same",
            "same",
        ),
    ),
)
def test_package_and_workspace_paths_are_isolated(
    tmp_path: Path,
    workspace_selector: str,
    package_selector: str,
) -> None:
    roots = prepare_roots(
        tmp_path
    )

    normal_workspace = (
        roots[
            "workspace_root"
        ]
    )

    normal_package = (
        roots[
            "package_root"
        ]
    )

    inside_repository_workspace = (
        roots[
            "repository_root"
        ]
        / "unsafe-workspace"
    )

    inside_repository_package = (
        roots[
            "repository_root"
        ]
        / "unsafe-packages"
    )

    shared = (
        tmp_path
        / "shared-output"
    )

    if workspace_selector == (
        "inside_repository"
    ):
        workspace_root = (
            inside_repository_workspace
        )
    elif workspace_selector == "same":
        workspace_root = shared
    else:
        workspace_root = (
            normal_workspace
        )

    if package_selector == (
        "inside_repository"
    ):
        package_root = (
            inside_repository_package
        )
    elif package_selector == "same":
        package_root = shared
    else:
        package_root = (
            normal_package
        )

    with pytest.raises(
        ValueError,
    ):
        CustomerDeploymentPackageService(
            mql5_source_root=(
                roots[
                    "source_root"
                ]
            ),
            platform_mql5_root=(
                roots[
                    "platform_root"
                ]
            ),
            workspace_root=(
                workspace_root
            ),
            package_root=(
                package_root
            ),
            compiler_runner=(
                compiler_runner
            ),
            provisioner=(
                make_provisioner()
            ),
            builder=make_builder(
                artifact_bytes_getter=(
                    lambda: b"EX5"
                )
            ),
        )


def test_published_lookup_rejects_package_with_extra_material(
    tmp_path: Path,
) -> None:
    service, _ = build_service(
        tmp_path
    )

    bootstrap_result = (
        make_bootstrap_result()
    )

    published = service.build_package(
        bootstrap_result=bootstrap_result
    )

    (
        published.artifact_path
        .parent
        / "unexpected.log"
    ).write_text(
        "must fail closed\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected material",
    ):
        service.get_published_package(
            deployment_id=(
                bootstrap_result
                .deployment
                .deployment_id
            ),
            agent_id=(
                bootstrap_result
                .deployment
                .agent_id
            ),
        )
