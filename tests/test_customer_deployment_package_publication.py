"""
TODOBA Customer Deployment Package Publication Tests

Proof:
- publication identity is deployment_id only
- deterministic package directory is stable
- missing publication returns None
- valid EX5-only publication returns real metadata
- unexpected package material fails closed
- empty published EX5 fails closed
- malformed package paths fail closed
- runtime publication contract accepts no agent_id

All filesystem state is isolated beneath tmp_path.
No MetaEditor, MQL5 source, secrets, or production data
are used.
"""

import hashlib
import inspect
from pathlib import Path

import pytest

from backend.commercial.customer_deployment_package_publication import (
    CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME,
    CustomerDeploymentPackagePublication,
    CustomerDeploymentPublishedPackage,
)


def expected_package_directory(
    *,
    package_root: Path,
    deployment_id: str,
) -> Path:
    digest = hashlib.sha256(
        deployment_id.encode("utf-8")
    ).hexdigest()

    return (
        package_root.resolve()
        / f"customer-deployment-{digest}"
    )


def publish_ex5(
    *,
    publication: CustomerDeploymentPackagePublication,
    deployment_id: str,
    artifact_bytes: bytes = b"TODOBA-PUBLISHED-EX5",
) -> Path:
    package_directory = publication.package_directory(
        deployment_id=deployment_id
    )

    package_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact_path = (
        package_directory
        / CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME
    )

    artifact_path.write_bytes(
        artifact_bytes
    )

    return artifact_path


def test_publication_requires_path_package_root(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="package_root must be Path",
    ):
        CustomerDeploymentPackagePublication(
            package_root=str(tmp_path),
        )


def test_existing_non_directory_package_root_is_rejected(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "packages"

    package_root.write_text(
        "not-a-directory",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="package_root must be a directory",
    ):
        CustomerDeploymentPackagePublication(
            package_root=package_root,
        )


def test_package_directory_is_deterministic(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "packages"

    publication = CustomerDeploymentPackagePublication(
        package_root=package_root,
    )

    deployment_id = "deployment-publication-001"

    assert publication.package_directory(
        deployment_id=deployment_id
    ) == expected_package_directory(
        package_root=package_root,
        deployment_id=deployment_id,
    )


def test_package_directory_normalizes_deployment_id(
    tmp_path: Path,
) -> None:
    publication = CustomerDeploymentPackagePublication(
        package_root=tmp_path / "packages",
    )

    assert publication.package_directory(
        deployment_id=" deployment-001 "
    ) == publication.package_directory(
        deployment_id="deployment-001"
    )


@pytest.mark.parametrize(
    "deployment_id",
    [
        "",
        "   ",
        None,
        123,
    ],
)
def test_invalid_deployment_id_is_rejected(
    tmp_path: Path,
    deployment_id,
) -> None:
    publication = CustomerDeploymentPackagePublication(
        package_root=tmp_path / "packages",
    )

    with pytest.raises(
        (
            TypeError,
            ValueError,
        )
    ):
        publication.package_directory(
            deployment_id=deployment_id
        )


def test_artifact_path_uses_authoritative_filename(
    tmp_path: Path,
) -> None:
    publication = CustomerDeploymentPackagePublication(
        package_root=tmp_path / "packages",
    )

    deployment_id = "deployment-publication-002"

    assert publication.artifact_path(
        deployment_id=deployment_id
    ) == (
        publication.package_directory(
            deployment_id=deployment_id
        )
        / "TODOBA_Trusted_Agent.ex5"
    )


def test_missing_publication_returns_none(
    tmp_path: Path,
) -> None:
    publication = CustomerDeploymentPackagePublication(
        package_root=tmp_path / "packages",
    )

    assert publication.get_published_package(
        deployment_id="deployment-missing"
    ) is None


def test_valid_published_ex5_returns_real_metadata(
    tmp_path: Path,
) -> None:
    publication = CustomerDeploymentPackagePublication(
        package_root=tmp_path / "packages",
    )

    deployment_id = "deployment-publication-003"
    artifact_bytes = b"TODOBA-RUNTIME-EX5"

    artifact_path = publish_ex5(
        publication=publication,
        deployment_id=deployment_id,
        artifact_bytes=artifact_bytes,
    )

    result = publication.get_published_package(
        deployment_id=deployment_id
    )

    assert isinstance(
        result,
        CustomerDeploymentPublishedPackage,
    )

    assert result.deployment_id == deployment_id
    assert result.artifact_path == artifact_path

    assert result.artifact_sha256 == hashlib.sha256(
        artifact_bytes
    ).hexdigest()

    assert result.artifact_size_bytes == len(
        artifact_bytes
    )


def test_unexpected_package_material_fails_closed(
    tmp_path: Path,
) -> None:
    publication = CustomerDeploymentPackagePublication(
        package_root=tmp_path / "packages",
    )

    deployment_id = "deployment-publication-004"

    publish_ex5(
        publication=publication,
        deployment_id=deployment_id,
    )

    package_directory = publication.package_directory(
        deployment_id=deployment_id
    )

    (
        package_directory
        / "unexpected-secret.txt"
    ).write_text(
        "must never be accepted",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected material",
    ):
        publication.get_published_package(
            deployment_id=deployment_id
        )


def test_wrong_package_file_fails_closed(
    tmp_path: Path,
) -> None:
    publication = CustomerDeploymentPackagePublication(
        package_root=tmp_path / "packages",
    )

    deployment_id = "deployment-publication-005"

    package_directory = publication.package_directory(
        deployment_id=deployment_id
    )

    package_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        package_directory
        / "wrong.ex5"
    ).write_bytes(
        b"WRONG"
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected material",
    ):
        publication.get_published_package(
            deployment_id=deployment_id
        )


def test_empty_published_ex5_fails_closed(
    tmp_path: Path,
) -> None:
    publication = CustomerDeploymentPackagePublication(
        package_root=tmp_path / "packages",
    )

    deployment_id = "deployment-publication-006"

    publish_ex5(
        publication=publication,
        deployment_id=deployment_id,
        artifact_bytes=b"",
    )

    with pytest.raises(
        RuntimeError,
        match="Published customer EX5 is empty",
    ):
        publication.get_published_package(
            deployment_id=deployment_id
        )


def test_package_path_that_is_file_fails_closed(
    tmp_path: Path,
) -> None:
    publication = CustomerDeploymentPackagePublication(
        package_root=tmp_path / "packages",
    )

    deployment_id = "deployment-publication-007"

    package_directory = publication.package_directory(
        deployment_id=deployment_id
    )

    package_directory.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    package_directory.write_text(
        "not-a-directory",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="Customer package path is not a directory",
    ):
        publication.get_published_package(
            deployment_id=deployment_id
        )


def test_package_root_shape_rechecked_at_read_time(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "packages"

    publication = CustomerDeploymentPackagePublication(
        package_root=package_root,
    )

    package_root.write_text(
        "invalid-after-construction",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="package_root is not a directory",
    ):
        publication.get_published_package(
            deployment_id="deployment-publication-008"
        )


def test_published_package_normalizes_metadata(
    tmp_path: Path,
) -> None:
    artifact_path = (
        tmp_path
        / "TODOBA_Trusted_Agent.ex5"
    )

    artifact_path.write_bytes(
        b"EX5"
    )

    result = CustomerDeploymentPublishedPackage(
        deployment_id=" deployment-001 ",
        artifact_path=artifact_path,
        artifact_sha256="A" * 64,
        artifact_size_bytes=3,
    )

    assert result.deployment_id == "deployment-001"
    assert result.artifact_sha256 == "a" * 64


def test_runtime_lookup_accepts_no_agent_or_customer_identity(
) -> None:
    parameters = inspect.signature(
        CustomerDeploymentPackagePublication
        .get_published_package
    ).parameters

    assert "deployment_id" in parameters
    assert "agent_id" not in parameters
    assert "customer_id" not in parameters
    assert "credential" not in parameters
    assert "bootstrap_result" not in parameters
    assert "compiler_runner" not in parameters