"""
Production composition owner for TODOBA VPS Connect.

This launcher wires the already-owned VPS Connect capabilities
into one standalone customer application graph.

It owns composition only.
"""

from pathlib import Path
from typing import Any

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightService,
)

from backend.commercial.customer_vps_connect_application_shell import (
    CustomerVPSConnectApplicationShell,
)

from backend.commercial.customer_vps_connect_core_orchestration_service import (
    CustomerVPSConnectCoreOrchestrationService,
)

from backend.commercial.customer_vps_connect_grant_http_client import (
    CustomerVPSConnectGrantHttpClient,
)

from backend.commercial.customer_vps_connect_gui_shell import (
    CustomerVPSConnectGuiShell,
)

from backend.commercial.customer_vps_connect_live_proof_http_client import (
    CustomerVPSConnectLiveProofHttpClient,
)

from backend.commercial.customer_vps_connect_mt5_account_identity_service import (
    CustomerVPSConnectMT5AccountIdentityService,
)

from backend.commercial.customer_vps_connect_mt5_detection_service import (
    CustomerVPSConnectMT5DetectionService,
)

from backend.commercial.customer_vps_connect_mt5_installed_agent_verifier import (
    CustomerVPSConnectMT5InstalledAgentVerifier,
)

from backend.commercial.customer_vps_connect_mt5_launcher_service import (
    CustomerVPSConnectMT5LauncherService,
)

from backend.commercial.customer_vps_connect_mt5_runtime_preparation_service import (
    CustomerVPSConnectMT5RuntimePreparationService,
)

from backend.commercial.customer_vps_connect_mt5_startup_config_service import (
    CustomerVPSConnectMT5StartupConfigService,
)

from backend.commercial.customer_vps_connect_mt5_symbol_discovery_service import (
    CustomerVPSConnectMT5SymbolDiscoveryService,
)

from backend.commercial.customer_vps_connect_windows_process_launcher import (
    CustomerVPSConnectWindowsProcessLauncher,
)


class CustomerVPSConnectLauncher:
    """
    Compose and launch one TODOBA VPS Connect customer process.
    """

    def __init__(
        self,
        *,
        cloud_base_url: str,
        roaming_appdata_path: Path,
        mt5_module: Any,
    ) -> None:
        if not isinstance(
            cloud_base_url,
            str,
        ):
            raise TypeError(
                "cloud_base_url must be str."
            )

        normalized_cloud_base_url = (
            cloud_base_url.strip()
        )

        if not normalized_cloud_base_url:
            raise ValueError(
                "cloud_base_url must not be empty."
            )

        if not isinstance(
            roaming_appdata_path,
            Path,
        ):
            raise TypeError(
                "roaming_appdata_path must be Path."
            )

        mt5_preflight_service = (
            CustomerMT5SetupPreflightService(
                mt5_module=mt5_module,
            )
        )

        detection_service = (
            CustomerVPSConnectMT5DetectionService(
                mt5_preflight_service=(
                    mt5_preflight_service
                ),
            )
        )

        account_identity_service = (
            CustomerVPSConnectMT5AccountIdentityService(
                mt5_preflight_service=(
                    mt5_preflight_service
                ),
            )
        )

        grant_http_client = (
            CustomerVPSConnectGrantHttpClient(
                cloud_base_url=(
                    normalized_cloud_base_url
                ),
            )
        )

        live_proof_http_client = (
            CustomerVPSConnectLiveProofHttpClient(
                cloud_base_url=(
                    normalized_cloud_base_url
                ),
            )
        )

        core_service = (
            CustomerVPSConnectCoreOrchestrationService(
                grant_http_client=grant_http_client,
                live_proof_http_client=(
                    live_proof_http_client
                ),
            )
        )

        installed_agent_verifier = (
            CustomerVPSConnectMT5InstalledAgentVerifier()
        )

        symbol_discovery_service = (
            CustomerVPSConnectMT5SymbolDiscoveryService(
                mt5_module=mt5_module,
            )
        )

        runtime_preparation_service = (
            CustomerVPSConnectMT5RuntimePreparationService()
        )

        startup_config_service = (
            CustomerVPSConnectMT5StartupConfigService()
        )

        windows_process_launcher = (
            CustomerVPSConnectWindowsProcessLauncher()
        )

        mt5_launcher_service = (
            CustomerVPSConnectMT5LauncherService(
                process_launcher=(
                    windows_process_launcher
                ),
            )
        )

        startup_config_directory = (
            roaming_appdata_path
            / "TODOBA"
            / "VPS Connect"
        )

        application_shell = (
            CustomerVPSConnectApplicationShell(
                detection_service=detection_service,
                account_identity_service=(
                    account_identity_service
                ),
                core_service=core_service,
                installed_agent_verifier=(
                    installed_agent_verifier
                ),
                symbol_discovery_service=(
                    symbol_discovery_service
                ),
                runtime_preparation_service=(
                    runtime_preparation_service
                ),
                startup_config_service=(
                    startup_config_service
                ),
                mt5_launcher_service=(
                    mt5_launcher_service
                ),
                startup_config_directory=(
                    startup_config_directory
                ),
            )
        )

        self._gui_shell = (
            CustomerVPSConnectGuiShell(
                application_shell=application_shell,
                roaming_appdata_path=(
                    roaming_appdata_path
                ),
            )
        )

    def run(
        self,
    ) -> None:
        self._gui_shell.run()
