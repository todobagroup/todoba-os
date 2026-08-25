"""
TODOBA Customer Deployment Package Publication

Owns the shared filesystem contract for one already
published customer-safe Trusted Agent package.

Publication identity:
    deployment_id

Deterministic layout:

    package_root
        / customer-deployment-<sha256(deployment_id)>
        / TODOBA_Trusted_Agent.ex5

Responsibilities:
- derive the deterministic package directory from deployment_id
- derive the authoritative published EX5 path
- validate existing package-directory material
- require an EX5-only published package
- read published artifact SHA-256 and size metadata
- fail closed on malformed or unsafe published package state

This component is runtime-safe and read-only.

This component does not:
- build or compile Trusted Agent artifacts
- access MetaEditor
- access MQL5 source trees
- create provisioning workspaces
- access deployment secrets
- accept agent_id from callers
- authenticate customers
- authorize deployment ownership or entitlement
- parse HTTP requests
- deliver files over HTTP
- mutate or publish package contents
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME = (
    "TODOBA_Trusted_Agent.ex5"
)


@dataclass(
    frozen=True,
)
class CustomerDeploymentPublishedPackage:
    """
    Read-only metadata for one published customer EX5.

    agent_id is intentionally absent. Agent ownership must
    come from an authoritative CustomerDeployment instead
    of package filesystem state or caller input.
    """

    deployment_id: str
    artifact_path: Path
    artifact_sha256: str
    artifact_size_bytes: int

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "deployment_id",
            self._normalize_required_string(
                self.deployment_id,
                name="deployment_id",
            ),
        )

        if not isinstance(
            self.artifact_path,
            Path,
        ):
            raise TypeError(
                "artifact_path must be Path."
            )

        if not isinstance(
            self.artifact_sha256,
            str,
        ):
            raise TypeError(
                "artifact_sha256 must be str."
            )

        digest = (
            self.artifact_sha256
            .strip()
            .lower()
        )

        if (
            len(digest) != 64
            or any(
                character
                not in "0123456789abcdef"
                for character in digest
            )
        ):
            raise ValueError(
                "artifact_sha256 must be a SHA-256 "
                "hexadecimal digest."
            )

        object.__setattr__(
            self,
            "artifact_sha256",
            digest,
        )

        if not isinstance(
            self.artifact_size_bytes,
            int,
        ):
            raise TypeError(
                "artifact_size_bytes must be int."
            )

        if self.artifact_size_bytes <= 0:
            raise ValueError(
                "artifact_size_bytes must be positive."
            )

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} is required."
            )

        return normalized


class CustomerDeploymentPackagePublication:
    """
    Read-only owner of the published package filesystem
    contract.
    """

    def __init__(
        self,
        *,
        package_root: Path,
    ) -> None:
        if not isinstance(
            package_root,
            Path,
        ):
            raise TypeError(
                "package_root must be Path."
            )

        self._package_root = (
            package_root.resolve()
        )

        if (
            self._package_root.exists()
            and not self._package_root.is_dir()
        ):
            raise ValueError(
                "package_root must be a directory."
            )

    @property
    def package_root(
        self,
    ) -> Path:
        return self._package_root

    def package_directory(
        self,
        *,
        deployment_id: str,
    ) -> Path:
        normalized_deployment_id = (
            self._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        return (
            self._package_root
            / self._deployment_key(
                normalized_deployment_id
            )
        )

    def artifact_path(
        self,
        *,
        deployment_id: str,
    ) -> Path:
        return (
            self.package_directory(
                deployment_id=deployment_id
            )
            / CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME
        )

    def validate_existing_package_directory(
        self,
        *,
        deployment_id: str,
    ) -> None:
        """
        Validate material already present for one package.

        A missing package directory is allowed because it
        means no package has been published yet.
        """

        package_directory = (
            self.package_directory(
                deployment_id=deployment_id
            )
        )

        if not package_directory.exists():
            return

        if not package_directory.is_dir():
            raise RuntimeError(
                "Customer package path is not "
                "a directory."
            )

        for item in package_directory.iterdir():
            if (
                not item.is_file()
                or item.name
                != CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME
            ):
                raise RuntimeError(
                    "Customer package contains "
                    "unexpected material."
                )

    def require_ex5_only_package(
        self,
        *,
        deployment_id: str,
    ) -> Path:
        """
        Require exactly one published Trusted Agent EX5.

        Returns the authoritative artifact path on success.
        """

        package_directory = (
            self.package_directory(
                deployment_id=deployment_id
            )
        )

        if not package_directory.is_dir():
            raise RuntimeError(
                "Customer package path is not "
                "a directory."
            )

        items = tuple(
            package_directory.iterdir()
        )

        if len(items) != 1:
            raise RuntimeError(
                "Customer package must contain "
                "exactly one artifact."
            )

        artifact = items[
            0
        ]

        if (
            not artifact.is_file()
            or artifact.name
            != CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME
        ):
            raise RuntimeError(
                "Customer package must contain only "
                "TODOBA_Trusted_Agent.ex5."
            )

        if artifact.stat().st_size <= 0:
            raise RuntimeError(
                "Published customer EX5 is empty."
            )

        return artifact

    def get_published_package(
        self,
        *,
        deployment_id: str,
    ) -> CustomerDeploymentPublishedPackage | None:
        """
        Read one already-published customer package.

        Missing package state returns None.
        Malformed existing package state fails closed.
        """

        normalized_deployment_id = (
            self._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        self._require_package_root_shape()

        package_directory = (
            self.package_directory(
                deployment_id=(
                    normalized_deployment_id
                )
            )
        )

        if not package_directory.exists():
            return None

        self.validate_existing_package_directory(
            deployment_id=(
                normalized_deployment_id
            )
        )

        artifact = (
            self.artifact_path(
                deployment_id=(
                    normalized_deployment_id
                )
            )
        )

        if not artifact.is_file():
            return None

        artifact = (
            self.require_ex5_only_package(
                deployment_id=(
                    normalized_deployment_id
                )
            )
        )

        return CustomerDeploymentPublishedPackage(
            deployment_id=(
                normalized_deployment_id
            ),
            artifact_path=artifact,
            artifact_sha256=(
                self._sha256(
                    artifact
                )
            ),
            artifact_size_bytes=(
                artifact.stat().st_size
            ),
        )

    def _require_package_root_shape(
        self,
    ) -> None:
        if (
            self._package_root.exists()
            and not self._package_root.is_dir()
        ):
            raise RuntimeError(
                "package_root is not a directory."
            )

    @staticmethod
    def _deployment_key(
        deployment_id: str,
    ) -> str:
        return (
            "customer-deployment-"
            + hashlib.sha256(
                deployment_id.encode(
                    "utf-8"
                )
            ).hexdigest()
        )

    @staticmethod
    def _sha256(
        path: Path,
    ) -> str:
        digest = hashlib.sha256()

        with path.open(
            "rb"
        ) as source:
            for chunk in iter(
                lambda: source.read(
                    1024 * 1024
                ),
                b"",
            ):
                digest.update(
                    chunk
                )

        return digest.hexdigest()

    @staticmethod
    def _normalize_required_string(
        value: str,
        *,
        name: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must be str."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{name} is required."
            )

        return normalized