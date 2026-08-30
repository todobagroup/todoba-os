"""
TODOBA Customer Setup Launcher

Composition owner for the customer-facing TODOBA Setup
application.

The launcher receives an already-created in-memory bootstrap
input plus local Windows/MT5 platform dependencies. It does
not acquire bootstrap secrets itself.

Composition flow:

    bootstrap input
        -> setup entry exchange
        -> authenticated setup HTTP transport
        -> verified EX5 installer
        -> setup orchestration
        -> MT5 HEDGING preflight
        -> application controller
        -> tkinter GUI shell

Installed means only that the authoritative TODOBA EX5
artifact was installed into the selected MT5 data path.
Runtime, online, VPS, attachment, and trading readiness are
outside this launcher boundary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallerService,
)
from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightService,
)
from backend.commercial.customer_setup_application_controller import (
    CustomerSetupApplicationController,
)
from backend.commercial.customer_setup_bootstrap_input import (
    CustomerSetupBootstrapInput,
)
from backend.commercial.customer_setup_entry_http_client import (
    CustomerSetupEntryHttpClient,
)
from backend.commercial.customer_setup_gui_shell import (
    CustomerSetupGuiShell,
)
from backend.commercial.customer_setup_http_client import (
    CustomerSetupHttpClient,
)
from backend.commercial.customer_setup_orchestration_service import (
    CustomerSetupOrchestrationService,
)


class CustomerSetupLauncher:
    """
    Production composition owner for one TODOBA Setup process.
    """

    __slots__ = (
        "_bootstrap_input",
        "_mt5_preflight_service",
        "_roaming_appdata_path",
    )

    def __init__(
        self,
        *,
        bootstrap_input: CustomerSetupBootstrapInput,
        mt5_module: Any,
        roaming_appdata_path: Path,
    ) -> None:
        if not isinstance(
            bootstrap_input,
            CustomerSetupBootstrapInput,
        ):
            raise TypeError(
                "bootstrap_input must be "
                "CustomerSetupBootstrapInput."
            )

        if not isinstance(
            roaming_appdata_path,
            Path,
        ):
            raise TypeError(
                "roaming_appdata_path must be Path."
            )

        # Validate the process-global MT5 bridge before any
        # launch credential is exchanged over the network.
        mt5_preflight_service = (
            CustomerMT5SetupPreflightService(
                mt5_module=mt5_module
            )
        )

        self._bootstrap_input = (
            bootstrap_input
        )
        self._mt5_preflight_service = (
            mt5_preflight_service
        )
        self._roaming_appdata_path = (
            roaming_appdata_path
        )

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerSetupLauncher("
            f"setup_base_url="
            f"{self._bootstrap_input.setup_base_url!r}, "
            "setup_launch_credential=<redacted>, "
            f"roaming_appdata_path="
            f"{self._roaming_appdata_path!r})"
        )

    def run(
        self,
    ) -> None:
        """
        Exchange setup entry authority, compose the customer
        Setup application, and run its GUI.
        """

        entry_client = (
            CustomerSetupEntryHttpClient(
                setup_base_url=(
                    self._bootstrap_input
                    .setup_base_url
                ),
                setup_launch_credential=(
                    self._bootstrap_input
                    .setup_launch_credential
                ),
            )
        )

        entry_result = (
            entry_client.exchange()
        )

        setup_http_client = (
            CustomerSetupHttpClient(
                setup_base_url=(
                    self._bootstrap_input
                    .setup_base_url
                ),
                setup_handoff_credential=(
                    entry_result
                    .handoff_credential
                ),
            )
        )

        ex5_installer_service = (
            CustomerMT5EX5InstallerService()
        )

        orchestration_service = (
            CustomerSetupOrchestrationService(
                setup_http_client=(
                    setup_http_client
                ),
                ex5_installer_service=(
                    ex5_installer_service
                ),
            )
        )

        controller = (
            CustomerSetupApplicationController(
                mt5_preflight_service=(
                    self._mt5_preflight_service
                ),
                setup_orchestration_service=(
                    orchestration_service
                ),
            )
        )

        gui_shell = CustomerSetupGuiShell(
            controller=controller,
            roaming_appdata_path=(
                self._roaming_appdata_path
            ),
        )

        gui_shell.run()