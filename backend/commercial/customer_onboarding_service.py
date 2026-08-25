"""
TODOBA Customer Onboarding Service

Owns one operator-controlled commercial onboarding
orchestration for a new customer deployment.

Orchestration:

    onboarding_request_id
    customer_id
    account_fingerprint
        -> CustomerDeploymentBootstrapService
        -> existing published package lookup
        -> build/publish package only when missing
        -> CustomerAccessProvisioningService
        -> one-time customer access credential

Safety rules:
- bootstrap owns deployment identity, secrets, account
  binding, enrollment, and retry recovery
- package service owns secure build and publication
- access provisioning owns customer identity, credential,
  and deployment entitlement activation
- package readiness is established before customer access
  entitlement is activated
- retry uses the same onboarding_request_id across
  bootstrap and access provisioning
- an already-published valid package is reused
- customer bearer plaintext is never persisted here
- deployment secret material is never returned here
- MT5 account fingerprint is never returned here
- server package paths are never returned here

This component does not:
- expose an HTTP API
- parse command-line arguments
- print credentials or secrets
- persist a duplicate onboarding store
- create payment or subscription state
- directly mutate deployment registries or entitlement
- directly compile MQL5 or invoke MetaEditor
"""

from dataclasses import dataclass
import threading

from backend.commercial.customer_access_provisioning_service import (
    CustomerAccessProvisioningService,
)
from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapService,
)
from backend.commercial.customer_deployment_package_service import (
    CustomerDeploymentPackageResult,
    CustomerDeploymentPackageService,
)


@dataclass(
    frozen=True,
    repr=False,
)
class CustomerOnboardingResult:
    """
    Operator-safe result for one completed onboarding.

    access_credential is one-time plaintext material and is
    deliberately redacted from repr().

    Deployment secrets, MT5 account fingerprint, and server
    package paths are deliberately absent.
    """

    onboarding_request_id: str
    customer_id: str
    deployment_id: str
    agent_id: str
    credential_id: str
    access_credential: str
    artifact_sha256: str
    artifact_size_bytes: int

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "onboarding_request_id",
            "customer_id",
            "deployment_id",
            "agent_id",
            "credential_id",
            "access_credential",
            "artifact_sha256",
        ):
            object.__setattr__(
                self,
                name,
                self._normalize_required_string(
                    getattr(
                        self,
                        name,
                    ),
                    name=name,
                ),
            )

        digest = (
            self.artifact_sha256
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

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerOnboardingResult("
            f"onboarding_request_id="
            f"{self.onboarding_request_id!r}, "
            f"customer_id={self.customer_id!r}, "
            f"deployment_id={self.deployment_id!r}, "
            f"agent_id={self.agent_id!r}, "
            f"credential_id={self.credential_id!r}, "
            "access_credential=<redacted>, "
            f"artifact_sha256={self.artifact_sha256!r}, "
            f"artifact_size_bytes="
            f"{self.artifact_size_bytes!r})"
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


class CustomerOnboardingService:
    """
    Coordinate one retry-safe customer onboarding.

    This owner intentionally composes existing commercial
    capabilities instead of duplicating their durable truth.
    """

    def __init__(
        self,
        *,
        bootstrap_service: (
            CustomerDeploymentBootstrapService
        ),
        package_service: (
            CustomerDeploymentPackageService
        ),
        access_provisioning_service: (
            CustomerAccessProvisioningService
        ),
    ) -> None:
        if not isinstance(
            bootstrap_service,
            CustomerDeploymentBootstrapService,
        ):
            raise TypeError(
                "bootstrap_service must be "
                "CustomerDeploymentBootstrapService."
            )

        if not isinstance(
            package_service,
            CustomerDeploymentPackageService,
        ):
            raise TypeError(
                "package_service must be "
                "CustomerDeploymentPackageService."
            )

        if not isinstance(
            access_provisioning_service,
            CustomerAccessProvisioningService,
        ):
            raise TypeError(
                "access_provisioning_service must be "
                "CustomerAccessProvisioningService."
            )

        self._bootstrap_service = (
            bootstrap_service
        )

        self._package_service = (
            package_service
        )

        self._access_provisioning_service = (
            access_provisioning_service
        )

        self._lock = threading.RLock()

    def onboard(
        self,
        *,
        onboarding_request_id: str,
        customer_id: str,
        account_fingerprint: str,
    ) -> CustomerOnboardingResult:
        """
        Complete one operator-controlled customer onboarding.

        Retry contract:
        - bootstrap reuses authoritative deployment identity
        - a valid existing package is reused
        - access provisioning reuses credential_id while
          rotating one-time bearer plaintext safely
        """

        normalized_request_id = (
            CustomerOnboardingResult
            ._normalize_required_string(
                onboarding_request_id,
                name="onboarding_request_id",
            )
        )

        normalized_customer_id = (
            CustomerOnboardingResult
            ._normalize_required_string(
                customer_id,
                name="customer_id",
            )
        )

        normalized_account_fingerprint = (
            CustomerOnboardingResult
            ._normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        with self._lock:
            bootstrap_result = (
                self._bootstrap_service.bootstrap(
                    enrollment_request_id=(
                        normalized_request_id
                    ),
                    customer_id=(
                        normalized_customer_id
                    ),
                    account_fingerprint=(
                        normalized_account_fingerprint
                    ),
                )
            )

            deployment = (
                bootstrap_result.deployment
            )

            if (
                deployment.customer_id
                != normalized_customer_id
            ):
                raise RuntimeError(
                    "Bootstrap deployment customer "
                    "identity mismatch."
                )

            package_result = (
                self._package_service
                .get_published_package(
                    deployment_id=(
                        deployment.deployment_id
                    ),
                    agent_id=(
                        deployment.agent_id
                    ),
                )
            )

            if package_result is None:
                package_result = (
                    self._package_service
                    .build_package(
                        bootstrap_result=(
                            bootstrap_result
                        )
                    )
                )

            self._validate_package_result(
                package_result=package_result,
                deployment_id=(
                    deployment.deployment_id
                ),
                agent_id=(
                    deployment.agent_id
                ),
            )

            access_result = (
                self._access_provisioning_service
                .provision(
                    provisioning_request_id=(
                        normalized_request_id
                    ),
                    customer_id=(
                        deployment.customer_id
                    ),
                    deployment_id=(
                        deployment.deployment_id
                    ),
                )
            )

            if (
                access_result.provisioning_request_id
                != normalized_request_id
            ):
                raise RuntimeError(
                    "Access provisioning request "
                    "identity mismatch."
                )

            if (
                access_result.customer_id
                != deployment.customer_id
            ):
                raise RuntimeError(
                    "Access provisioning customer "
                    "identity mismatch."
                )

            if (
                access_result.deployment_id
                != deployment.deployment_id
            ):
                raise RuntimeError(
                    "Access provisioning deployment "
                    "identity mismatch."
                )

            return CustomerOnboardingResult(
                onboarding_request_id=(
                    normalized_request_id
                ),
                customer_id=(
                    deployment.customer_id
                ),
                deployment_id=(
                    deployment.deployment_id
                ),
                agent_id=(
                    deployment.agent_id
                ),
                credential_id=(
                    access_result.credential_id
                ),
                access_credential=(
                    access_result.access_credential
                ),
                artifact_sha256=(
                    package_result.artifact_sha256
                ),
                artifact_size_bytes=(
                    package_result.artifact_size_bytes
                ),
            )

    @staticmethod
    def _validate_package_result(
        *,
        package_result: CustomerDeploymentPackageResult,
        deployment_id: str,
        agent_id: str,
    ) -> None:
        if not isinstance(
            package_result,
            CustomerDeploymentPackageResult,
        ):
            raise RuntimeError(
                "Package service returned invalid result."
            )

        if (
            package_result.deployment_id
            != deployment_id
        ):
            raise RuntimeError(
                "Published package deployment identity "
                "mismatch."
            )

        if (
            package_result.agent_id
            != agent_id
        ):
            raise RuntimeError(
                "Published package Trusted Agent identity "
                "mismatch."
            )
