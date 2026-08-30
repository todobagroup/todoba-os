"""
TODOBA Customer Setup Application Controller

Provides the customer-application boundary above the existing
MT5 preflight and customer setup orchestration owners.

Flow:

    discover standard MT5 installations
        -> project customer-safe installation options
        -> customer selects one exact option
        -> preflight selected terminal
        -> run customer setup orchestration
        -> build_pending or installed

This owner is intentionally stateless. A later customer-facing
presentation layer may call discovery again or retry the selected
terminal when package preparation is still pending.

This component does not:
- own HTTP transport
- install deployment artifacts
- build packages
- persist commercial state
- expose server routes
- start or attach the trading agent
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallationResult,
)
from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5InstallationCandidate,
    CustomerMT5SetupPreflightResult,
    CustomerMT5SetupPreflightService,
)
from backend.commercial.customer_setup_orchestration_service import (
    CustomerSetupOrchestrationResult,
    CustomerSetupOrchestrationService,
)


@dataclass(
    frozen=True,
)
class CustomerSetupInstallationOption:
    """
    Customer-safe selectable MT5 installation.

    origin_path is deliberately not projected from discovery
    because it is internal discovery evidence rather than a
    customer choice.
    """

    installation_path: str
    terminal_path: str
    portable: bool

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "installation_path",
            _normalize_required_string(
                self.installation_path,
                name="installation_path",
            ),
        )

        object.__setattr__(
            self,
            "terminal_path",
            _normalize_required_string(
                self.terminal_path,
                name="terminal_path",
            ),
        )

        if not isinstance(
            self.portable,
            bool,
        ):
            raise TypeError(
                "portable must be bool."
            )


@dataclass(
    frozen=True,
)
class CustomerSetupApplicationResult:
    """
    Customer-safe result for one selected-terminal attempt.

    build_pending:
        The selected account passed MT5 preflight but its
        deployment package is not ready yet.

    installed:
        The authoritative deployment artifact was installed
        into the selected MT5 data path.

    installed does not mean that the agent is running,
    connected, or trading-ready.
    """

    status: Literal[
        "build_pending",
        "installed",
    ]

    terminal_path: str
    login: int
    server: str
    account_fingerprint: str

    installed_path: str | None = None
    already_present: bool | None = None

    def __post_init__(
        self,
    ) -> None:
        if self.status not in (
            "build_pending",
            "installed",
        ):
            raise ValueError(
                "Unsupported customer setup application status."
            )

        for field_name in (
            "terminal_path",
            "server",
            "account_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_required_string(
                    getattr(
                        self,
                        field_name,
                    ),
                    name=field_name,
                ),
            )

        if (
            not isinstance(
                self.login,
                int,
            )
            or isinstance(
                self.login,
                bool,
            )
            or self.login <= 0
        ):
            raise ValueError(
                "login must be a positive integer."
            )

        if self.status == "build_pending":
            if (
                self.installed_path is not None
                or self.already_present is not None
            ):
                raise ValueError(
                    "build_pending must not contain "
                    "installation fields."
                )

            return

        normalized_installed_path = (
            _normalize_required_string(
                self.installed_path,
                name="installed_path",
            )
        )

        object.__setattr__(
            self,
            "installed_path",
            normalized_installed_path,
        )

        if not isinstance(
            self.already_present,
            bool,
        ):
            raise ValueError(
                "installed requires already_present bool."
            )


class CustomerSetupApplicationController:
    """
    Stateless customer Setup application boundary.
    """

    def __init__(
        self,
        *,
        mt5_preflight_service: CustomerMT5SetupPreflightService,
        setup_orchestration_service: CustomerSetupOrchestrationService,
    ) -> None:
        if not isinstance(
            mt5_preflight_service,
            CustomerMT5SetupPreflightService,
        ):
            raise TypeError(
                "mt5_preflight_service must be "
                "CustomerMT5SetupPreflightService."
            )

        if not isinstance(
            setup_orchestration_service,
            CustomerSetupOrchestrationService,
        ):
            raise TypeError(
                "setup_orchestration_service must be "
                "CustomerSetupOrchestrationService."
            )

        self._mt5_preflight_service = (
            mt5_preflight_service
        )
        self._setup_orchestration_service = (
            setup_orchestration_service
        )

    def discover_standard_installations(
        self,
        *,
        roaming_appdata_path: Path,
    ) -> tuple[
        CustomerSetupInstallationOption,
        ...,
    ]:
        if not isinstance(
            roaming_appdata_path,
            Path,
        ):
            raise TypeError(
                "roaming_appdata_path must be Path."
            )

        discovered = (
            self._mt5_preflight_service
            .discover_standard_installations(
                roaming_appdata_path=(
                    roaming_appdata_path
                ),
            )
        )

        if not isinstance(
            discovered,
            tuple,
        ):
            raise RuntimeError(
                "MT5 preflight service returned invalid "
                "discovery result."
            )

        options = []

        for candidate in discovered:
            if not isinstance(
                candidate,
                CustomerMT5InstallationCandidate,
            ):
                raise RuntimeError(
                    "MT5 discovery returned invalid candidate."
                )

            options.append(
                CustomerSetupInstallationOption(
                    installation_path=(
                        candidate.installation_path
                    ),
                    terminal_path=(
                        candidate.terminal_path
                    ),
                    portable=(
                        candidate.portable
                    ),
                )
            )

        return tuple(
            options
        )

    def run_selected(
        self,
        *,
        option: CustomerSetupInstallationOption,
    ) -> CustomerSetupApplicationResult:
        if not isinstance(
            option,
            CustomerSetupInstallationOption,
        ):
            raise TypeError(
                "option must be "
                "CustomerSetupInstallationOption."
            )

        preflight_result = (
            self._mt5_preflight_service.preflight(
                terminal_path=Path(
                    option.terminal_path
                ),
                portable=option.portable,
            )
        )

        if not isinstance(
            preflight_result,
            CustomerMT5SetupPreflightResult,
        ):
            raise RuntimeError(
                "MT5 preflight service returned invalid "
                "preflight result."
            )

        orchestration_result = (
            self._setup_orchestration_service.run(
                preflight_result=(
                    preflight_result
                ),
            )
        )

        if not isinstance(
            orchestration_result,
            CustomerSetupOrchestrationResult,
        ):
            raise RuntimeError(
                "Customer setup orchestration returned "
                "invalid result."
            )

        if (
            orchestration_result.status
            == "build_pending"
        ):
            return (
                CustomerSetupApplicationResult(
                    status="build_pending",
                    terminal_path=(
                        preflight_result.terminal_path
                    ),
                    login=preflight_result.login,
                    server=preflight_result.server,
                    account_fingerprint=(
                        preflight_result
                        .account_fingerprint
                    ),
                )
            )

        if (
            orchestration_result.status
            != "installed"
        ):
            raise RuntimeError(
                "Customer setup orchestration returned "
                "unsupported status."
            )

        installation_result = (
            orchestration_result
            .installation_result
        )

        self._require_converged_installation(
            preflight_result=preflight_result,
            installation_result=(
                installation_result
            ),
        )

        return CustomerSetupApplicationResult(
            status="installed",
            terminal_path=(
                preflight_result.terminal_path
            ),
            login=preflight_result.login,
            server=preflight_result.server,
            account_fingerprint=(
                preflight_result.account_fingerprint
            ),
            installed_path=(
                installation_result.installed_path
            ),
            already_present=(
                installation_result.already_present
            ),
        )

    @staticmethod
    def _require_converged_installation(
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
        installation_result,
    ) -> None:
        if not isinstance(
            installation_result,
            CustomerMT5EX5InstallationResult,
        ):
            raise RuntimeError(
                "Installed orchestration result does not "
                "contain valid installation evidence."
            )

        if (
            installation_result.terminal_path
            != preflight_result.terminal_path
        ):
            raise RuntimeError(
                "Installation terminal identity does not "
                "match MT5 preflight."
            )

        if (
            installation_result.account_fingerprint
            != preflight_result.account_fingerprint
        ):
            raise RuntimeError(
                "Installation account identity does not "
                "match MT5 preflight."
            )


def _normalize_required_string(
    value,
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