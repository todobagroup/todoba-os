"""
TODOBA Customer Deployment Package Service

Builds one customer-safe Trusted Agent artifact from a
prepared or completed commercial bootstrap.

Architecture:

Customer Deployment Bootstrap Result
    -> isolated temporary provisioning workspace
    -> existing Trusted Agent provisioner
    -> existing secure deployment builder
    -> validated EX5
    -> atomic customer package publication

Security boundaries:

- source provisioning happens only in a temporary workspace
- temporary workspace must be outside the repository
- customer package storage must be outside the repository
- customer package contains only TODOBA_Trusted_Agent.ex5
- no MQ5 source is published
- no MQH credential header is published
- no MetaEditor compile log is published
- temporary provisioning/build material is always removed
- an existing valid package survives a failed rebuild
- final publication uses atomic file replacement

This component does not:
- authenticate customers
- expose an HTTP download API
- generate deployment identity or secrets
- own commercial enrollment
- reimplement provisioning or MetaEditor compilation
- purchase or migrate MetaTrader Virtual Hosting
"""

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import threading
import uuid

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapPreparationResult,
    CustomerDeploymentBootstrapResult,
)
from backend.commercial.customer_deployment_package_publication import (
    CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME,
    CustomerDeploymentPackagePublication,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
)
from scripts.build_trusted_agent_deployment import (
    build_trusted_agent_deployment,
)
from scripts.provision_trusted_agent_deployment import (
    provision_trusted_agent_deployment,
)


_ARTIFACT_NAME = (
    CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME
)
_PUBLISH_STAGING_DIRECTORY = ".staging"


Provisioner = Callable[
    ...,
    Path,
]

Builder = Callable[
    ...,
    Path,
]

CompilerRunner = Callable[
    ...,
    int,
]


@dataclass(
    frozen=True,
)
class CustomerDeploymentPackageResult:
    """
    Public metadata for one customer-safe EX5 package.

    Secret material and MT5 account fingerprint are
    intentionally excluded.
    """

    deployment_id: str
    agent_id: str
    artifact_path: Path
    artifact_sha256: str
    artifact_size_bytes: int

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "deployment_id",
            "agent_id",
            "artifact_sha256",
        ):
            value = getattr(
                self,
                name,
            )

            if not isinstance(
                value,
                str,
            ):
                raise TypeError(
                    f"{name} must be str."
                )

            if not value.strip():
                raise ValueError(
                    f"{name} is required."
                )

        if not isinstance(
            self.artifact_path,
            Path,
        ):
            raise TypeError(
                "artifact_path must be Path."
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

        digest = self.artifact_sha256.lower()

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


class CustomerDeploymentPackageService:
    """
    Build and atomically publish one Trusted Agent EX5.

    Provisioning and compilation are delegated to the
    existing secure deployment machinery.

    Every build attempt receives a fresh temporary root.
    The final package path is stable for deployment_id.
    """

    def __init__(
        self,
        *,
        mql5_source_root: Path,
        platform_mql5_root: Path,
        workspace_root: Path,
        package_root: Path,
        compiler_runner: CompilerRunner,
        provisioner: Provisioner = (
            provision_trusted_agent_deployment
        ),
        builder: Builder = (
            build_trusted_agent_deployment
        ),
    ) -> None:
        for name, value in (
            (
                "mql5_source_root",
                mql5_source_root,
            ),
            (
                "platform_mql5_root",
                platform_mql5_root,
            ),
            (
                "workspace_root",
                workspace_root,
            ),
            (
                "package_root",
                package_root,
            ),
        ):
            if not isinstance(
                value,
                Path,
            ):
                raise TypeError(
                    f"{name} must be Path."
                )

        if not callable(
            compiler_runner
        ):
            raise TypeError(
                "compiler_runner must be callable."
            )

        if not callable(
            provisioner
        ):
            raise TypeError(
                "provisioner must be callable."
            )

        if not callable(
            builder
        ):
            raise TypeError(
                "builder must be callable."
            )

        self._mql5_source_root = (
            mql5_source_root.resolve()
        )

        self._platform_mql5_root = (
            platform_mql5_root.resolve()
        )

        self._workspace_root = (
            workspace_root.resolve()
        )

        self._package_root = (
            package_root.resolve()
        )

        self._publication = (
            CustomerDeploymentPackagePublication(
                package_root=self._package_root
            )
        )

        self._compiler_runner = (
            compiler_runner
        )

        self._provisioner = (
            provisioner
        )

        self._builder = (
            builder
        )

        self._lock = threading.RLock()

        self._validate_static_paths()

    def build_package(
        self,
        *,
        bootstrap_result: (
            CustomerDeploymentBootstrapResult
            | CustomerDeploymentBootstrapPreparationResult
        ),
    ) -> CustomerDeploymentPackageResult:
        """
        Build and publish one customer-safe EX5 artifact.

        A failed rebuild never replaces an already
        published package.

        Temporary source, credential headers, build logs,
        and isolated MQL5 material are removed in finally.
        """

        (
            deployment,
            deployment_secrets,
            account_fingerprint,
        ) = self._validate_bootstrap_result(
            bootstrap_result
        )

        with self._lock:
            package_directory = (
                self._publication.package_directory(
                    deployment_id=(
                        deployment.deployment_id
                    )
                )
            )

            final_artifact = (
                package_directory
                / _ARTIFACT_NAME
            )

            # Validate any existing customer package before
            # creating build/workspace state. An unsafe
            # package must fail with zero build side-effect.
            self._publication.validate_existing_package_directory(
                deployment_id=(
                    deployment.deployment_id
                )
            )

            self._workspace_root.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._package_root.mkdir(
                parents=True,
                exist_ok=True,
            )

            attempt_root = Path(
                tempfile.mkdtemp(
                    prefix=(
                        "todoba-customer-package-"
                    ),
                    dir=self._workspace_root,
                )
            ).resolve()

            publish_temp_path: Path | None = None

            try:
                provision_output_root = (
                    attempt_root
                    / "provisioned"
                )

                deployment_root = (
                    self._provisioner(
                        mql5_source_root=(
                            self._mql5_source_root
                        ),
                        output_root=(
                            provision_output_root
                        ),
                        agent_id=(
                            deployment.agent_id
                        ),
                        account_fingerprint=(
                            account_fingerprint
                        ),
                        agent_secret=(
                            deployment_secrets
                            .agent_secret
                        ),
                        execution_mission_signing_secret=(
                            deployment_secrets
                            .execution_mission_signing_secret
                        ),
                        control_mission_signing_secret=(
                            deployment_secrets
                            .control_mission_signing_secret
                        ),
                    )
                )

                if not isinstance(
                    deployment_root,
                    Path,
                ):
                    raise RuntimeError(
                        "Trusted Agent provisioner did "
                        "not return a Path."
                    )

                deployment_root = (
                    deployment_root.resolve()
                )

                expected_deployment_root = (
                    provision_output_root
                    / deployment.agent_id
                ).resolve()

                if (
                    deployment_root
                    != expected_deployment_root
                ):
                    raise RuntimeError(
                        "Trusted Agent provisioner "
                        "returned an unexpected "
                        "deployment root."
                    )

                build_root = (
                    attempt_root
                    / "build"
                )

                built_artifact = (
                    self._builder(
                        deployment_root=(
                            deployment_root
                        ),
                        platform_mql5_root=(
                            self._platform_mql5_root
                        ),
                        build_root=build_root,
                        compiler_runner=(
                            self._compiler_runner
                        ),
                    )
                )

                if not isinstance(
                    built_artifact,
                    Path,
                ):
                    raise RuntimeError(
                        "Trusted Agent builder did not "
                        "return a Path."
                    )

                built_artifact = (
                    built_artifact.resolve()
                )

                expected_built_artifact = (
                    deployment_root
                    / "artifact"
                    / _ARTIFACT_NAME
                ).resolve()

                if (
                    built_artifact
                    != expected_built_artifact
                ):
                    raise RuntimeError(
                        "Trusted Agent builder returned "
                        "an unexpected artifact path."
                    )

                self._validate_built_artifact(
                    artifact_path=(
                        built_artifact
                    ),
                    deployment_root=(
                        deployment_root
                    ),
                    build_root=build_root,
                )

                artifact_size = (
                    built_artifact
                    .stat()
                    .st_size
                )

                artifact_sha256 = (
                    self._sha256(
                        built_artifact
                    )
                )

                staging_root = (
                    self._package_root
                    / _PUBLISH_STAGING_DIRECTORY
                )

                if (
                    staging_root.exists()
                    and not staging_root.is_dir()
                ):
                    raise RuntimeError(
                        "Customer package staging path "
                        "is not a directory."
                    )

                staging_root.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                publish_temp_path = (
                    staging_root
                    / (
                        f"{package_directory.name}"
                        f"-{uuid.uuid4().hex}.tmp"
                    )
                )

                shutil.copy2(
                    built_artifact,
                    publish_temp_path,
                )

                if (
                    not publish_temp_path.is_file()
                ):
                    raise RuntimeError(
                        "Customer package staging copy "
                        "was not created."
                    )

                if (
                    publish_temp_path
                    .stat()
                    .st_size
                    != artifact_size
                ):
                    raise RuntimeError(
                        "Customer package staging size "
                        "verification failed."
                    )

                if (
                    self._sha256(
                        publish_temp_path
                    )
                    != artifact_sha256
                ):
                    raise RuntimeError(
                        "Customer package staging hash "
                        "verification failed."
                    )

                package_directory.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                self._publication.validate_existing_package_directory(
                    deployment_id=(
                        deployment.deployment_id
                    )
                )

                os.replace(
                    publish_temp_path,
                    final_artifact,
                )

                publish_temp_path = None

                if not final_artifact.is_file():
                    raise RuntimeError(
                        "Customer EX5 package was not "
                        "published."
                    )

                if (
                    final_artifact
                    .stat()
                    .st_size
                    != artifact_size
                ):
                    raise RuntimeError(
                        "Published customer EX5 size "
                        "verification failed."
                    )

                if (
                    self._sha256(
                        final_artifact
                    )
                    != artifact_sha256
                ):
                    raise RuntimeError(
                        "Published customer EX5 hash "
                        "verification failed."
                    )

                self._publication.require_ex5_only_package(
                    deployment_id=(
                        deployment.deployment_id
                    )
                )

                return CustomerDeploymentPackageResult(
                    deployment_id=(
                        deployment.deployment_id
                    ),
                    agent_id=(
                        deployment.agent_id
                    ),
                    artifact_path=(
                        final_artifact
                    ),
                    artifact_sha256=(
                        artifact_sha256
                    ),
                    artifact_size_bytes=(
                        artifact_size
                    ),
                )

            finally:
                if (
                    publish_temp_path
                    is not None
                    and publish_temp_path.exists()
                ):
                    publish_temp_path.unlink()

                if attempt_root.exists():
                    shutil.rmtree(
                        attempt_root
                    )

    def get_published_package(
        self,
        *,
        deployment_id: str,
        agent_id: str,
    ) -> CustomerDeploymentPackageResult | None:
        """
        Return metadata for an already published package.

        Filesystem publication truth is delegated to the
        shared runtime-safe publication owner.
        """

        normalized_deployment_id = (
            self._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        normalized_agent_id = (
            self._normalize_required_string(
                agent_id,
                name="agent_id",
            )
        )

        published = (
            self._publication
            .get_published_package(
                deployment_id=(
                    normalized_deployment_id
                )
            )
        )

        if published is None:
            return None

        return CustomerDeploymentPackageResult(
            deployment_id=(
                published.deployment_id
            ),
            agent_id=(
                normalized_agent_id
            ),
            artifact_path=(
                published.artifact_path
            ),
            artifact_sha256=(
                published.artifact_sha256
            ),
            artifact_size_bytes=(
                published.artifact_size_bytes
            ),
        )

    def _validate_bootstrap_result(
        self,
        bootstrap_result: (
            CustomerDeploymentBootstrapResult
            | CustomerDeploymentBootstrapPreparationResult
        ),
    ) -> tuple[
        CustomerDeployment,
        CustomerDeploymentSecrets,
        str,
    ]:
        if not isinstance(
            bootstrap_result,
            (
                CustomerDeploymentBootstrapResult,
                CustomerDeploymentBootstrapPreparationResult,
            ),
        ):
            raise TypeError(
                "bootstrap_result must be "
                "CustomerDeploymentBootstrapResult or "
                "CustomerDeploymentBootstrapPreparationResult."
            )

        deployment = (
            bootstrap_result.deployment
        )

        deployment_secrets = (
            bootstrap_result.secrets
        )

        if not isinstance(
            deployment,
            CustomerDeployment,
        ):
            raise TypeError(
                "Bootstrap deployment must be "
                "CustomerDeployment."
            )

        if not isinstance(
            deployment_secrets,
            CustomerDeploymentSecrets,
        ):
            raise TypeError(
                "Bootstrap secrets must be "
                "CustomerDeploymentSecrets."
            )

        if (
            deployment_secrets.deployment_id
            != deployment.deployment_id
        ):
            raise ValueError(
                "Bootstrap secret identity does not "
                "match deployment identity."
            )

        account_fingerprint = (
            self._normalize_required_string(
                bootstrap_result
                .account_fingerprint,
                name="account_fingerprint",
            )
        )

        return (
            deployment,
            deployment_secrets,
            account_fingerprint,
        )

    def _validate_static_paths(
        self,
    ) -> None:
        if not self._mql5_source_root.is_dir():
            raise FileNotFoundError(
                "MQL5 source root does not exist."
            )

        if not self._platform_mql5_root.is_dir():
            raise FileNotFoundError(
                "Platform MQL5 root does not exist."
            )

        repository_root = (
            self._mql5_source_root.parent
        )

        for name, path in (
            (
                "workspace_root",
                self._workspace_root,
            ),
            (
                "package_root",
                self._package_root,
            ),
        ):
            if (
                path == repository_root
                or repository_root
                in path.parents
            ):
                raise ValueError(
                    f"{name} must be outside "
                    "the repository."
                )

        if self._paths_overlap(
            self._mql5_source_root,
            self._platform_mql5_root,
        ):
            raise ValueError(
                "Platform MQL5 root must not overlap "
                "TODOBA source MQL5 root."
            )

        if self._paths_overlap(
            self._workspace_root,
            self._package_root,
        ):
            raise ValueError(
                "workspace_root and package_root "
                "must not overlap."
            )

        for protected_path in (
            self._mql5_source_root,
            self._platform_mql5_root,
        ):
            if self._paths_overlap(
                self._workspace_root,
                protected_path,
            ):
                raise ValueError(
                    "workspace_root overlaps a "
                    "protected MQL5 root."
                )

            if self._paths_overlap(
                self._package_root,
                protected_path,
            ):
                raise ValueError(
                    "package_root overlaps a "
                    "protected MQL5 root."
                )

    def _validate_built_artifact(
        self,
        *,
        artifact_path: Path,
        deployment_root: Path,
        build_root: Path,
    ) -> None:
        if not artifact_path.is_file():
            raise RuntimeError(
                "Trusted Agent EX5 artifact is missing."
            )

        if artifact_path.name != _ARTIFACT_NAME:
            raise RuntimeError(
                "Trusted Agent artifact has an "
                "unexpected filename."
            )

        if artifact_path.stat().st_size <= 0:
            raise RuntimeError(
                "Trusted Agent EX5 artifact is empty."
            )

        if (
            deployment_root
            / "MQL5"
        ).exists():
            raise RuntimeError(
                "Provisioned MQL5 source material "
                "survived secure build cleanup."
            )

        if build_root.exists():
            raise RuntimeError(
                "Isolated build workspace survived "
                "secure build cleanup."
            )

        artifact_directory = (
            artifact_path.parent
        )

        artifact_files = tuple(
            path
            for path in artifact_directory.iterdir()
            if path.is_file()
        )

        if artifact_files != (
            artifact_path,
        ):
            raise RuntimeError(
                "Secure build artifact directory "
                "contains unexpected files."
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
    def _paths_overlap(
        first: Path,
        second: Path,
    ) -> bool:
        first = first.resolve()
        second = second.resolve()

        return (
            first == second
            or first in second.parents
            or second in first.parents
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
