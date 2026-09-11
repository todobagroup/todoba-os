"""
TODOBA VPS Connect toolkit-neutral application shell.

Owns only customer-flow sequencing:

Open -> Detect -> Connect -> Verify -> Finish

It delegates technical authority to the existing VPS Connect
detection, account identity, and Core orchestration owners.

Activation Code and account fingerprint are never retained by
this shell.
"""

from pathlib import Path

from backend.commercial.customer_vps_connect_migration_observation_service import (
    CustomerVPSConnectMigrationObservationResult,
    CustomerVPSConnectMigrationObservationService,
)
from typing import Any

from backend.commercial.customer_vps_connect_core_orchestration_service import (
    CustomerVPSConnectCoreLiveProofResult,
    CustomerVPSConnectCoreOrchestrationResult,
    CustomerVPSConnectCoreOrchestrationService,
)

from backend.commercial.customer_vps_connect_mt5_account_identity_service import (
    CustomerVPSConnectMT5AccountIdentityService,
)

from backend.commercial.customer_vps_connect_mt5_detection_service import (
    CustomerVPSConnectMT5DetectionResult,
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


def _required_string(
    value: Any,
    *,
    name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise RuntimeError(
            f"{name} is invalid."
        )

    normalized = value.strip()

    if not normalized:
        raise RuntimeError(
            f"{name} is invalid."
        )

    return normalized


class CustomerVPSConnectApplicationShell:
    """
    Reusable customer-flow shell for standalone and embedded use.
    """

    def __init__(
        self,
        *,
        detection_service: CustomerVPSConnectMT5DetectionService,
        account_identity_service: CustomerVPSConnectMT5AccountIdentityService,
        core_service: CustomerVPSConnectCoreOrchestrationService,
        installed_agent_verifier: (
            CustomerVPSConnectMT5InstalledAgentVerifier | None
        ) = None,
        symbol_discovery_service: (
            CustomerVPSConnectMT5SymbolDiscoveryService | None
        ) = None,
        runtime_preparation_service: (
            CustomerVPSConnectMT5RuntimePreparationService | None
        ) = None,
        startup_config_service: (
            CustomerVPSConnectMT5StartupConfigService | None
        ) = None,
        mt5_launcher_service: (
            CustomerVPSConnectMT5LauncherService | None
        ) = None,
        startup_config_directory: Path | None = None,
        migration_observation_service: (
            CustomerVPSConnectMigrationObservationService | None
        ) = None,
    ) -> None:
        if not isinstance(
            detection_service,
            CustomerVPSConnectMT5DetectionService,
        ):
            raise TypeError(
                "detection_service must be "
                "CustomerVPSConnectMT5DetectionService."
            )

        if not isinstance(
            account_identity_service,
            CustomerVPSConnectMT5AccountIdentityService,
        ):
            raise TypeError(
                "account_identity_service must be "
                "CustomerVPSConnectMT5AccountIdentityService."
            )

        if not isinstance(
            core_service,
            CustomerVPSConnectCoreOrchestrationService,
        ):
            raise TypeError(
                "core_service must be "
                "CustomerVPSConnectCoreOrchestrationService."
            )

        if (
            migration_observation_service is not None
            and not isinstance(
                migration_observation_service,
                CustomerVPSConnectMigrationObservationService,
            )
        ):
            raise TypeError(
                "migration_observation_service must be "
                "CustomerVPSConnectMigrationObservationService."
            )

        auto_runtime_dependencies = (
            installed_agent_verifier,
            symbol_discovery_service,
            runtime_preparation_service,
            startup_config_service,
            mt5_launcher_service,
            startup_config_directory,
        )

        dependency_presence = tuple(
            value is not None
            for value in auto_runtime_dependencies
        )

        if any(
            dependency_presence
        ) and not all(
            dependency_presence
        ):
            raise ValueError(
                "AUTO-1 runtime dependencies must be "
                "provided together."
            )

        self._auto_runtime_enabled = all(
            dependency_presence
        )

        if self._auto_runtime_enabled:
            if not isinstance(
                installed_agent_verifier,
                CustomerVPSConnectMT5InstalledAgentVerifier,
            ):
                raise TypeError(
                    "installed_agent_verifier must be "
                    "CustomerVPSConnectMT5InstalledAgentVerifier."
                )

            if not isinstance(
                symbol_discovery_service,
                CustomerVPSConnectMT5SymbolDiscoveryService,
            ):
                raise TypeError(
                    "symbol_discovery_service must be "
                    "CustomerVPSConnectMT5SymbolDiscoveryService."
                )

            if not isinstance(
                runtime_preparation_service,
                CustomerVPSConnectMT5RuntimePreparationService,
            ):
                raise TypeError(
                    "runtime_preparation_service must be "
                    "CustomerVPSConnectMT5RuntimePreparationService."
                )

            if not isinstance(
                startup_config_service,
                CustomerVPSConnectMT5StartupConfigService,
            ):
                raise TypeError(
                    "startup_config_service must be "
                    "CustomerVPSConnectMT5StartupConfigService."
                )

            if not isinstance(
                mt5_launcher_service,
                CustomerVPSConnectMT5LauncherService,
            ):
                raise TypeError(
                    "mt5_launcher_service must be "
                    "CustomerVPSConnectMT5LauncherService."
                )

            if not isinstance(
                startup_config_directory,
                Path,
            ):
                raise TypeError(
                    "startup_config_directory must be Path."
                )

        self._detection_service = detection_service
        self._account_identity_service = (
            account_identity_service
        )
        self._core_service = core_service

        self._installed_agent_verifier = (
            installed_agent_verifier
        )
        self._symbol_discovery_service = (
            symbol_discovery_service
        )
        self._runtime_preparation_service = (
            runtime_preparation_service
        )
        self._startup_config_service = (
            startup_config_service
        )
        self._mt5_launcher_service = (
            mt5_launcher_service
        )
        self._startup_config_directory = (
            startup_config_directory
        )

        self._migration_observation_service = (
            migration_observation_service
        )

        self._opened = False
        self._detected = False
        self._connected = False

    def __repr__(
        self,
    ) -> str:
        if self._connected:
            state = "connected"
        elif self._detected:
            state = "detected"
        elif self._opened:
            state = "opened"
        else:
            state = "closed"

        return (
            "CustomerVPSConnectApplicationShell("
            f"state={state!r})"
        )

    def open(
        self,
    ) -> None:
        self._opened = True

    def detect(
        self,
        *,
        roaming_appdata_path: Path,
    ) -> CustomerVPSConnectMT5DetectionResult:
        if not self._opened:
            raise RuntimeError(
                "VPS Connect application is not open."
            )

        result = self._detection_service.detect(
            roaming_appdata_path=roaming_appdata_path,
        )

        self._detected = True

        return result

    def connect(
        self,
        *,
        activation_code: str,
        option: Any,
    ) -> CustomerVPSConnectCoreOrchestrationResult:
        if not self._opened:
            raise RuntimeError(
                "VPS Connect application is not open."
            )

        if not self._detected:
            raise RuntimeError(
                "MT5 detection is required before connect."
            )

        if not self._auto_runtime_enabled:
            identity_result = (
                self._account_identity_service.probe(
                    option=option,
                )
            )

            account_fingerprint = _required_string(
                getattr(
                    identity_result,
                    "account_fingerprint",
                    None,
                ),
                name="account_fingerprint",
            )

            result = self._core_service.prepare(
                activation_code=activation_code,
                account_fingerprint=account_fingerprint,
            )

            if not isinstance(
                result,
                CustomerVPSConnectCoreOrchestrationResult,
            ):
                raise RuntimeError(
                    "VPS Connect Core returned invalid "
                    "connect result."
                )

            self._connected = True

            return result

        binding = (
            self._account_identity_service.probe_binding(
                option=option,
            )
        )

        identity_result = getattr(
            binding,
            "identity",
            None,
        )

        preflight_result = getattr(
            binding,
            "preflight_result",
            None,
        )

        account_fingerprint = _required_string(
            getattr(
                identity_result,
                "account_fingerprint",
                None,
            ),
            name="account_fingerprint",
        )

        result = self._core_service.prepare(
            activation_code=activation_code,
            account_fingerprint=account_fingerprint,
        )

        if not isinstance(
            result,
            CustomerVPSConnectCoreOrchestrationResult,
        ):
            raise RuntimeError(
                "VPS Connect Core returned invalid "
                "connect result."
            )

        installation_result = (
            self._installed_agent_verifier.verify(
                preflight_result=preflight_result,
            )
        )

        symbols = (
            self._symbol_discovery_service.discover(
                preflight_result=preflight_result,
            )
        )

        preparation_result = (
            self._runtime_preparation_service.prepare(
                preflight_result=preflight_result,
                installation_result=installation_result,
            )
        )

        gold_symbol = (
            self._runtime_preparation_service.select_gold_symbol(
                symbols=symbols,
            )
        )

        startup_plan = (
            self._runtime_preparation_service.build_startup_plan(
                preparation_result=preparation_result,
                symbol=gold_symbol,
            )
        )

        config_text = (
            self._runtime_preparation_service.render_startup_config(
                startup_plan=startup_plan,
            )
        )

        config_result = (
            self._startup_config_service.write(
                directory=self._startup_config_directory,
                config_text=config_text,
            )
        )

        config_path = _required_string(
            getattr(
                config_result,
                "config_path",
                None,
            ),
            name="config_path",
        )

        terminal_path = _required_string(
            getattr(
                preparation_result,
                "terminal_path",
                None,
            ),
            name="terminal_path",
        )

        self._mt5_launcher_service.launch(
            terminal_path=terminal_path,
            config_path=config_path,
        )

        self._connected = True

        return result

    def verify(
        self,
    ) -> CustomerVPSConnectCoreLiveProofResult:
        if not self._connected:
            raise RuntimeError(
                "VPS Connect must be connected before verify."
            )

        result = self._core_service.check_live_proof()

        if not isinstance(
            result,
            CustomerVPSConnectCoreLiveProofResult,
        ):
            raise RuntimeError(
                "VPS Connect Core returned invalid "
                "live proof result."
            )

        return result

    def begin_migration_observation(
        self,
    ) -> None:
        if not self._connected:
            raise RuntimeError(
                "VPS Connect must be connected before "
                "migration observation."
            )

        if self._migration_observation_service is None:
            raise RuntimeError(
                "VPS migration observation is not configured."
            )

        self._migration_observation_service.begin()

    def observe_migration(
        self,
    ) -> CustomerVPSConnectMigrationObservationResult:
        if not self._connected:
            raise RuntimeError(
                "VPS Connect must be connected before "
                "migration observation."
            )

        if self._migration_observation_service is None:
            raise RuntimeError(
                "VPS migration observation is not configured."
            )

        result = (
            self._migration_observation_service.observe()
        )

        if not isinstance(
            result,
            CustomerVPSConnectMigrationObservationResult,
        ):
            raise RuntimeError(
                "VPS migration observation returned "
                "invalid result."
            )

        return result

    def finish(
        self,
    ) -> None:
        if not self._connected:
            raise RuntimeError(
                "VPS Connect must be connected before finish."
            )

        readiness = (
            self._core_service.finish_readiness()
        )

        if readiness.status != "finish_ready":
            raise RuntimeError(
                "VPS Connect is not ready to finish."
            )
