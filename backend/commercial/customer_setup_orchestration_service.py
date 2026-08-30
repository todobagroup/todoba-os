"""
TODOBA Customer Setup Orchestration Service

Coordinates already-authoritative customer setup owners in this order:

    validated MT5 preflight result
        -> provision customer setup
        -> build_pending: stop and return
        -> ready: download package
        -> install verified package
        -> installed

Ownership boundaries:
- MT5 discovery and preflight happen before this service
- HTTP transport belongs to CustomerSetupHttpClient
- EX5 filesystem installation belongs to CustomerMT5EX5InstallerService
- this service does not poll, sleep, retry, persist state, or expose HTTP
- installed means artifact installed only, not agent runtime readiness
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallationResult,
    CustomerMT5EX5InstallerService,
)
from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)
from backend.commercial.customer_setup_http_client import (
    CustomerSetupHttpClient,
    CustomerSetupProvisioningTransportResult,
)


@dataclass(
    frozen=True,
)
class CustomerSetupOrchestrationResult:
    """
    Customer-safe result for one orchestration attempt.

    build_pending:
        Server-side deployment package is not ready yet.

    installed:
        Authoritative package bytes were verified and installed.
        This does not mean the agent is running or trading-ready.
    """

    status: Literal[
        "build_pending",
        "installed",
    ]
    installation_result: (
        CustomerMT5EX5InstallationResult | None
    ) = None

    def __post_init__(
        self,
    ) -> None:
        if self.status not in (
            "build_pending",
            "installed",
        ):
            raise ValueError(
                "Unsupported customer setup orchestration status."
            )

        if self.status == "build_pending":
            if self.installation_result is not None:
                raise ValueError(
                    "build_pending must not contain installation result."
                )

            return

        if not isinstance(
            self.installation_result,
            CustomerMT5EX5InstallationResult,
        ):
            raise ValueError(
                "installed requires "
                "CustomerMT5EX5InstallationResult."
            )


class CustomerSetupOrchestrationService:
    """
    Coordinate provisioning, package download, and installation.
    """

    def __init__(
        self,
        *,
        setup_http_client: CustomerSetupHttpClient,
        ex5_installer_service: CustomerMT5EX5InstallerService,
    ) -> None:
        if not isinstance(
            setup_http_client,
            CustomerSetupHttpClient,
        ):
            raise TypeError(
                "setup_http_client must be "
                "CustomerSetupHttpClient."
            )

        if not isinstance(
            ex5_installer_service,
            CustomerMT5EX5InstallerService,
        ):
            raise TypeError(
                "ex5_installer_service must be "
                "CustomerMT5EX5InstallerService."
            )

        self._setup_http_client = setup_http_client
        self._ex5_installer_service = (
            ex5_installer_service
        )

    def run(
        self,
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
    ) -> CustomerSetupOrchestrationResult:
        if not isinstance(
            preflight_result,
            CustomerMT5SetupPreflightResult,
        ):
            raise TypeError(
                "preflight_result must be "
                "CustomerMT5SetupPreflightResult."
            )

        provisioning_result = (
            self._setup_http_client.provision(
                account_fingerprint=(
                    preflight_result.account_fingerprint
                ),
            )
        )

        if not isinstance(
            provisioning_result,
            CustomerSetupProvisioningTransportResult,
        ):
            raise RuntimeError(
                "Customer setup HTTP client returned invalid "
                "provisioning result."
            )

        if provisioning_result.status == "build_pending":
            return CustomerSetupOrchestrationResult(
                status="build_pending",
            )

        if provisioning_result.status != "ready":
            raise RuntimeError(
                "Customer setup provisioning result has "
                "unsupported status."
            )

        artifact_sha256 = (
            provisioning_result.artifact_sha256
        )
        artifact_size_bytes = (
            provisioning_result.artifact_size_bytes
        )

        if (
            not isinstance(
                artifact_sha256,
                str,
            )
            or not isinstance(
                artifact_size_bytes,
                int,
            )
            or isinstance(
                artifact_size_bytes,
                bool,
            )
        ):
            raise RuntimeError(
                "Ready customer setup provisioning result "
                "is missing artifact metadata."
            )

        artifact_bytes = (
            self._setup_http_client.download_package()
        )

        if not isinstance(
            artifact_bytes,
            bytes,
        ):
            raise RuntimeError(
                "Customer setup HTTP client returned invalid "
                "package bytes."
            )

        installation_result = (
            self._ex5_installer_service.install(
                preflight_result=preflight_result,
                artifact_bytes=artifact_bytes,
                expected_sha256=artifact_sha256,
                expected_size_bytes=(
                    artifact_size_bytes
                ),
            )
        )

        self._require_converged_installation(
            preflight_result=preflight_result,
            provisioning_result=provisioning_result,
            installation_result=installation_result,
        )

        return CustomerSetupOrchestrationResult(
            status="installed",
            installation_result=installation_result,
        )

    @staticmethod
    def _require_converged_installation(
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
        provisioning_result: (
            CustomerSetupProvisioningTransportResult
        ),
        installation_result,
    ) -> None:
        if not isinstance(
            installation_result,
            CustomerMT5EX5InstallationResult,
        ):
            raise RuntimeError(
                "Customer EX5 installer returned invalid result."
            )

        if (
            installation_result.account_fingerprint
            != preflight_result.account_fingerprint
        ):
            raise RuntimeError(
                "Installed artifact account identity does not "
                "match MT5 preflight."
            )

        if (
            installation_result.terminal_path
            != preflight_result.terminal_path
        ):
            raise RuntimeError(
                "Installed artifact terminal does not match "
                "MT5 preflight."
            )

        if (
            installation_result.artifact_sha256
            != provisioning_result.artifact_sha256
        ):
            raise RuntimeError(
                "Installed artifact SHA-256 does not match "
                "authoritative provisioning metadata."
            )

        if (
            installation_result.artifact_size_bytes
            != provisioning_result.artifact_size_bytes
        ):
            raise RuntimeError(
                "Installed artifact size does not match "
                "authoritative provisioning metadata."
            )