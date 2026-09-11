from pathlib import Path

import backend.commercial.customer_vps_connect_launcher as launcher_module

from backend.commercial.customer_vps_connect_launcher import (
    CustomerVPSConnectLauncher,
)


CLOUD_BASE_URL = "https://api.todobagroup.com"

ROAMING = Path(
    r"C:\Users\Customer\AppData\Roaming"
)

EXPECTED_CONFIG_DIRECTORY = (
    ROAMING
    / "TODOBA"
    / "VPS Connect"
)

MT5_MODULE = object()


class _FakeBase:
    instances = []

    @classmethod
    def reset(cls):
        cls.instances = []


class FakePreflight(_FakeBase):
    instances = []

    def __init__(
        self,
        *,
        mt5_module,
    ):
        self.mt5_module = mt5_module
        type(self).instances.append(self)


class FakeDetection(_FakeBase):
    instances = []

    def __init__(
        self,
        *,
        mt5_preflight_service,
    ):
        self.mt5_preflight_service = (
            mt5_preflight_service
        )
        type(self).instances.append(self)


class FakeIdentity(_FakeBase):
    instances = []

    def __init__(
        self,
        *,
        mt5_preflight_service,
    ):
        self.mt5_preflight_service = (
            mt5_preflight_service
        )
        type(self).instances.append(self)


class FakeGrantClient(_FakeBase):
    instances = []

    def __init__(
        self,
        *,
        cloud_base_url,
    ):
        self.cloud_base_url = cloud_base_url
        type(self).instances.append(self)


class FakeLiveProofClient(_FakeBase):
    instances = []

    def __init__(
        self,
        *,
        cloud_base_url,
    ):
        self.cloud_base_url = cloud_base_url
        type(self).instances.append(self)


class FakeCore(_FakeBase):
    instances = []

    def __init__(
        self,
        *,
        grant_http_client,
        live_proof_http_client,
    ):
        self.grant_http_client = (
            grant_http_client
        )
        self.live_proof_http_client = (
            live_proof_http_client
        )
        type(self).instances.append(self)


class FakeInstalledAgentVerifier(_FakeBase):
    instances = []

    def __init__(self):
        type(self).instances.append(self)


class FakeSymbolDiscovery(_FakeBase):
    instances = []

    def __init__(
        self,
        *,
        mt5_module,
    ):
        self.mt5_module = mt5_module
        type(self).instances.append(self)


class FakeRuntimePreparation(_FakeBase):
    instances = []

    def __init__(self):
        type(self).instances.append(self)


class FakeStartupConfig(_FakeBase):
    instances = []

    def __init__(self):
        type(self).instances.append(self)


class FakeWindowsProcessLauncher(_FakeBase):
    instances = []

    def __init__(self):
        type(self).instances.append(self)


class FakeMT5Launcher(_FakeBase):
    instances = []

    def __init__(
        self,
        *,
        process_launcher,
    ):
        self.process_launcher = (
            process_launcher
        )
        type(self).instances.append(self)


class FakeApplicationShell(_FakeBase):
    instances = []

    def __init__(
        self,
        **kwargs,
    ):
        self.kwargs = dict(kwargs)
        type(self).instances.append(self)


class FakeGuiShell(_FakeBase):
    instances = []

    def __init__(
        self,
        *,
        application_shell,
        roaming_appdata_path,
    ):
        self.application_shell = (
            application_shell
        )
        self.roaming_appdata_path = (
            roaming_appdata_path
        )
        type(self).instances.append(self)

    def run(self):
        pass


ALL_FAKES = (
    FakePreflight,
    FakeDetection,
    FakeIdentity,
    FakeGrantClient,
    FakeLiveProofClient,
    FakeCore,
    FakeInstalledAgentVerifier,
    FakeSymbolDiscovery,
    FakeRuntimePreparation,
    FakeStartupConfig,
    FakeWindowsProcessLauncher,
    FakeMT5Launcher,
    FakeApplicationShell,
    FakeGuiShell,
)


def _patch(
    monkeypatch,
):
    for fake in ALL_FAKES:
        fake.reset()

    replacements = {
        "CustomerMT5SetupPreflightService": (
            FakePreflight
        ),
        "CustomerVPSConnectMT5DetectionService": (
            FakeDetection
        ),
        "CustomerVPSConnectMT5AccountIdentityService": (
            FakeIdentity
        ),
        "CustomerVPSConnectGrantHttpClient": (
            FakeGrantClient
        ),
        "CustomerVPSConnectLiveProofHttpClient": (
            FakeLiveProofClient
        ),
        "CustomerVPSConnectCoreOrchestrationService": (
            FakeCore
        ),
        "CustomerVPSConnectMT5InstalledAgentVerifier": (
            FakeInstalledAgentVerifier
        ),
        "CustomerVPSConnectMT5SymbolDiscoveryService": (
            FakeSymbolDiscovery
        ),
        "CustomerVPSConnectMT5RuntimePreparationService": (
            FakeRuntimePreparation
        ),
        "CustomerVPSConnectMT5StartupConfigService": (
            FakeStartupConfig
        ),
        "CustomerVPSConnectWindowsProcessLauncher": (
            FakeWindowsProcessLauncher
        ),
        "CustomerVPSConnectMT5LauncherService": (
            FakeMT5Launcher
        ),
        "CustomerVPSConnectApplicationShell": (
            FakeApplicationShell
        ),
        "CustomerVPSConnectGuiShell": (
            FakeGuiShell
        ),
    }

    for name, replacement in replacements.items():
        monkeypatch.setattr(
            launcher_module,
            name,
            replacement,
            raising=False,
        )


def test_launcher_wires_complete_auto_runtime_graph(
    monkeypatch,
):
    _patch(
        monkeypatch
    )

    CustomerVPSConnectLauncher(
        cloud_base_url=CLOUD_BASE_URL,
        roaming_appdata_path=ROAMING,
        mt5_module=MT5_MODULE,
    )

    assert len(
        FakeInstalledAgentVerifier.instances
    ) == 1

    assert len(
        FakeSymbolDiscovery.instances
    ) == 1

    assert (
        FakeSymbolDiscovery.instances[0].mt5_module
        is MT5_MODULE
    )

    assert len(
        FakeRuntimePreparation.instances
    ) == 1

    assert len(
        FakeStartupConfig.instances
    ) == 1

    assert len(
        FakeWindowsProcessLauncher.instances
    ) == 1

    assert len(
        FakeMT5Launcher.instances
    ) == 1

    assert (
        FakeMT5Launcher.instances[0].process_launcher
        is FakeWindowsProcessLauncher.instances[0]
    )

    assert len(
        FakeApplicationShell.instances
    ) == 1

    application = (
        FakeApplicationShell.instances[0]
    )

    assert (
        application.kwargs[
            "installed_agent_verifier"
        ]
        is FakeInstalledAgentVerifier.instances[0]
    )

    assert (
        application.kwargs[
            "symbol_discovery_service"
        ]
        is FakeSymbolDiscovery.instances[0]
    )

    assert (
        application.kwargs[
            "runtime_preparation_service"
        ]
        is FakeRuntimePreparation.instances[0]
    )

    assert (
        application.kwargs[
            "startup_config_service"
        ]
        is FakeStartupConfig.instances[0]
    )

    assert (
        application.kwargs[
            "mt5_launcher_service"
        ]
        is FakeMT5Launcher.instances[0]
    )

    assert (
        application.kwargs[
            "startup_config_directory"
        ]
        == EXPECTED_CONFIG_DIRECTORY
    )


def test_launcher_keeps_one_shared_mt5_module_boundary(
    monkeypatch,
):
    _patch(
        monkeypatch
    )

    CustomerVPSConnectLauncher(
        cloud_base_url=CLOUD_BASE_URL,
        roaming_appdata_path=ROAMING,
        mt5_module=MT5_MODULE,
    )

    assert len(
        FakePreflight.instances
    ) == 1

    assert (
        FakePreflight.instances[0].mt5_module
        is MT5_MODULE
    )

    assert (
        FakeSymbolDiscovery.instances[0].mt5_module
        is MT5_MODULE
    )


def test_launcher_remains_composition_only():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_launcher.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "subprocess",
        "Popen",
        "write_text",
        "write_bytes",
        "mkdir(",
        "terminate(",
        "kill(",
        "common.ini",
        "WebRequestUrl",
        "MetaTrader5.initialize",
    ):
        assert forbidden not in source
