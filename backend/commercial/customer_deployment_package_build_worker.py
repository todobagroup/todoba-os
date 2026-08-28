"""
TODOBA Customer Deployment Package Build Worker

Processes exactly one immutable customer package build
request identified by deployment_id.

Architecture:

BuildRequestStore.get(deployment_id)
    -> PackagePublication READY check
    -> recover prepared bootstrap
    -> validate request/bootstrap identity
    -> acquire deployment-scoped OS build lock
    -> re-check PackagePublication inside lock
    -> PackageService.build_package(prepared)
    -> require authoritative publication evidence
    -> validate build/publication convergence

Package publication is the durable READY/DONE evidence.

This worker intentionally owns no mutable job status.

Result statuses:
- BUILT
- ALREADY_READY
- BUSY

This component does not:
- enumerate the build request store
- own a worker loop or scheduler
- persist DONE state
- use time-based leases
- activate customer deployments
- provision customer access
- mutate entitlement
- bind setup activation
- authenticate HTTP requests
- parse customer requests
- own MetaEditor configuration
- invoke MetaEditor directly
- generate deployment identity or secrets
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapPreparationResult,
    CustomerDeploymentBootstrapService,
)
from backend.commercial.customer_deployment_package_build_lock import (
    CustomerDeploymentPackageBuildLockManager,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
    CustomerDeploymentPackageBuildRequestStore,
)
from backend.commercial.customer_deployment_package_publication import (
    CustomerDeploymentPackagePublication,
    CustomerDeploymentPublishedPackage,
)
from backend.commercial.customer_deployment_package_service import (
    CustomerDeploymentPackageResult,
    CustomerDeploymentPackageService,
)


class CustomerDeploymentPackageBuildWorkerStatus(
    str,
    Enum,
):
    BUILT = "BUILT"
    ALREADY_READY = "ALREADY_READY"
    BUSY = "BUSY"


@dataclass(
    frozen=True,
)
class CustomerDeploymentPackageBuildWorkerResult:
    deployment_id: str
    status: CustomerDeploymentPackageBuildWorkerStatus

    def __post_init__(
        self,
    ) -> None:
        normalized_deployment_id = (
            self._normalize_required_string(
                self.deployment_id,
                name="deployment_id",
            )
        )

        object.__setattr__(
            self,
            "deployment_id",
            normalized_deployment_id,
        )

        if not isinstance(
            self.status,
            CustomerDeploymentPackageBuildWorkerStatus,
        ):
            raise TypeError(
                "status must be "
                "CustomerDeploymentPackageBuildWorkerStatus."
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


class CustomerDeploymentPackageBuildWorker:
    """
    Process one immutable package build request safely.

    The worker deliberately performs the first publication
    lookup before bootstrap recovery. Therefore a historical
    immutable build request remains harmless after its
    deployment has later become active: an already-published
    package converges immediately to ALREADY_READY without
    touching the prepared-bootstrap recovery boundary.
    """

    def __init__(
        self,
        *,
        build_request_store: (
            CustomerDeploymentPackageBuildRequestStore
        ),
        build_lock_manager: (
            CustomerDeploymentPackageBuildLockManager
        ),
        bootstrap_service: CustomerDeploymentBootstrapService,
        package_service: CustomerDeploymentPackageService,
        package_publication: (
            CustomerDeploymentPackagePublication
        ),
    ) -> None:
        self._require_owner_method(
            build_request_store,
            owner_name="build_request_store",
            method_name="get",
        )

        self._require_owner_method(
            build_lock_manager,
            owner_name="build_lock_manager",
            method_name="acquire",
        )

        self._require_owner_method(
            bootstrap_service,
            owner_name="bootstrap_service",
            method_name="recover_prepared_bootstrap",
        )

        self._require_owner_method(
            package_service,
            owner_name="package_service",
            method_name="build_package",
        )

        self._require_owner_method(
            package_publication,
            owner_name="package_publication",
            method_name="get_published_package",
        )

        self._build_request_store = (
            build_request_store
        )

        self._build_lock_manager = (
            build_lock_manager
        )

        self._bootstrap_service = (
            bootstrap_service
        )

        self._package_service = (
            package_service
        )

        self._package_publication = (
            package_publication
        )

    def process(
        self,
        *,
        deployment_id: str,
    ) -> CustomerDeploymentPackageBuildWorkerResult:
        normalized_deployment_id = (
            CustomerDeploymentPackageBuildWorkerResult
            ._normalize_required_string(
                deployment_id,
                name="deployment_id",
            )
        )

        request = self._build_request_store.get(
            deployment_id=(
                normalized_deployment_id
            )
        )

        if request is None:
            raise RuntimeError(
                "Customer package build request is missing."
            )

        self._validate_request(
            request=request,
            deployment_id=(
                normalized_deployment_id
            ),
        )

        published = (
            self._package_publication
            .get_published_package(
                deployment_id=(
                    normalized_deployment_id
                )
            )
        )

        if published is not None:
            self._validate_publication(
                published=published,
                deployment_id=(
                    normalized_deployment_id
                ),
            )

            return self._result(
                deployment_id=(
                    normalized_deployment_id
                ),
                status=(
                    CustomerDeploymentPackageBuildWorkerStatus
                    .ALREADY_READY
                ),
            )

        prepared = (
            self._bootstrap_service
            .recover_prepared_bootstrap(
                enrollment_request_id=(
                    request.bootstrap_request_id
                )
            )
        )

        self._validate_prepared_bootstrap(
            prepared=prepared,
            request=request,
        )

        build_lock = (
            self._build_lock_manager.acquire(
                deployment_id=(
                    normalized_deployment_id
                )
            )
        )

        if build_lock is None:
            return self._result(
                deployment_id=(
                    normalized_deployment_id
                ),
                status=(
                    CustomerDeploymentPackageBuildWorkerStatus
                    .BUSY
                ),
            )

        with build_lock:
            # Another process may have completed publication
            # between our first READY check and lock
            # acquisition. Re-check under the authoritative
            # deployment-scoped OS lock before any build.
            published = (
                self._package_publication
                .get_published_package(
                    deployment_id=(
                        normalized_deployment_id
                    )
                )
            )

            if published is not None:
                self._validate_publication(
                    published=published,
                    deployment_id=(
                        normalized_deployment_id
                    ),
                )

                return self._result(
                    deployment_id=(
                        normalized_deployment_id
                    ),
                    status=(
                        CustomerDeploymentPackageBuildWorkerStatus
                        .ALREADY_READY
                    ),
                )

            package_result = (
                self._package_service.build_package(
                    bootstrap_result=prepared
                )
            )

            self._validate_build_result(
                package_result=package_result,
                prepared=prepared,
                deployment_id=(
                    normalized_deployment_id
                ),
            )

            published = (
                self._package_publication
                .get_published_package(
                    deployment_id=(
                        normalized_deployment_id
                    )
                )
            )

            if published is None:
                raise RuntimeError(
                    "Customer package build completed "
                    "without authoritative publication."
                )

            self._validate_publication(
                published=published,
                deployment_id=(
                    normalized_deployment_id
                ),
            )

            self._validate_build_publication_match(
                package_result=package_result,
                published=published,
            )

            return self._result(
                deployment_id=(
                    normalized_deployment_id
                ),
                status=(
                    CustomerDeploymentPackageBuildWorkerStatus
                    .BUILT
                ),
            )

    @staticmethod
    def _validate_request(
        *,
        request: CustomerDeploymentPackageBuildRequest,
        deployment_id: str,
    ) -> None:
        if not isinstance(
            request,
            CustomerDeploymentPackageBuildRequest,
        ):
            raise RuntimeError(
                "Customer package build request store "
                "returned invalid request."
            )

        if request.deployment_id != deployment_id:
            raise RuntimeError(
                "Customer package build request deployment "
                "identity mismatch."
            )

    @staticmethod
    def _validate_prepared_bootstrap(
        *,
        prepared: CustomerDeploymentBootstrapPreparationResult,
        request: CustomerDeploymentPackageBuildRequest,
    ) -> None:
        if not isinstance(
            prepared,
            CustomerDeploymentBootstrapPreparationResult,
        ):
            raise RuntimeError(
                "Prepared bootstrap recovery returned "
                "invalid result."
            )

        if (
            prepared.enrollment_request_id
            != request.bootstrap_request_id
        ):
            raise RuntimeError(
                "Prepared bootstrap request identity "
                "does not match package build request."
            )

        if (
            prepared.deployment.deployment_id
            != request.deployment_id
        ):
            raise RuntimeError(
                "Prepared bootstrap deployment identity "
                "does not match package build request."
            )

    @staticmethod
    def _validate_build_result(
        *,
        package_result: CustomerDeploymentPackageResult,
        prepared: CustomerDeploymentBootstrapPreparationResult,
        deployment_id: str,
    ) -> None:
        if not isinstance(
            package_result,
            CustomerDeploymentPackageResult,
        ):
            raise RuntimeError(
                "Package service returned invalid "
                "build result."
            )

        if package_result.deployment_id != deployment_id:
            raise RuntimeError(
                "Built package deployment identity "
                "mismatch."
            )

        if (
            package_result.agent_id
            != prepared.deployment.agent_id
        ):
            raise RuntimeError(
                "Built package agent identity mismatch."
            )

    @staticmethod
    def _validate_publication(
        *,
        published: CustomerDeploymentPublishedPackage,
        deployment_id: str,
    ) -> None:
        if not isinstance(
            published,
            CustomerDeploymentPublishedPackage,
        ):
            raise RuntimeError(
                "Package publication owner returned "
                "invalid evidence."
            )

        if published.deployment_id != deployment_id:
            raise RuntimeError(
                "Published package deployment identity "
                "mismatch."
            )

    @staticmethod
    def _validate_build_publication_match(
        *,
        package_result: CustomerDeploymentPackageResult,
        published: CustomerDeploymentPublishedPackage,
    ) -> None:
        if (
            package_result.deployment_id
            != published.deployment_id
        ):
            raise RuntimeError(
                "Build result and publication deployment "
                "identity mismatch."
            )

        if (
            package_result.artifact_path
            != published.artifact_path
        ):
            raise RuntimeError(
                "Build result and publication artifact "
                "path mismatch."
            )

        if (
            package_result.artifact_sha256
            != published.artifact_sha256
        ):
            raise RuntimeError(
                "Build result and publication artifact "
                "hash mismatch."
            )

        if (
            package_result.artifact_size_bytes
            != published.artifact_size_bytes
        ):
            raise RuntimeError(
                "Build result and publication artifact "
                "size mismatch."
            )

    @staticmethod
    def _result(
        *,
        deployment_id: str,
        status: CustomerDeploymentPackageBuildWorkerStatus,
    ) -> CustomerDeploymentPackageBuildWorkerResult:
        return CustomerDeploymentPackageBuildWorkerResult(
            deployment_id=deployment_id,
            status=status,
        )

    @staticmethod
    def _require_owner_method(
        owner,
        *,
        owner_name: str,
        method_name: str,
    ) -> None:
        method = getattr(
            owner,
            method_name,
            None,
        )

        if not callable(
            method
        ):
            raise TypeError(
                f"{owner_name} must expose callable "
                f"{method_name}()."
            )
