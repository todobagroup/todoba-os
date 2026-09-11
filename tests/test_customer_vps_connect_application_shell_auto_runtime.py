from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.commercial.customer_vps_connect_application_shell import (
    CustomerVPSConnectApplicationShell,
)

from backend.commercial.customer_vps_connect_core_orchestration_service import (
    CustomerVPSConnectCoreOrchestrationResult,
    CustomerVPSConnectCoreOrchestrationService,
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


ROAMING = Path(
    r"C:\Users\Customer\AppData\Roaming"
)

CONFIG_DIRECTORY = Path(
    r"C:\Users\Customer\AppData\Roaming\TODOBA"
)

ACTIVATION_CODE = "activation-secret"
ACCOUNT_FINGERPRINT = "Broker-Pro:12345678"
TERMINAL_PATH = r"C:\MT5\terminal64.exe"
DATA_PATH = r"C:\MT5-DATA"
INSTALLED_PATH = (
    DATA_PATH
    + r"\MQL5\Experts\TODOBA_Trusted_Agent.ex5"
)
CONFIG_PATH = (
    str(CONFIG_DIRECTORY)
    + r"\TODOBA_VPS_Startup.ini"
)

OPTION = object()
DETECTION_RESULT = object()
PREFLIGHT_RESULT = object()


class FakeDetectionService(
    CustomerVPSConnectMT5DetectionService
):
    def __init__(self):
        self.calls = []

    def detect(
        self,
        *,
        roaming_appdata_path,
    ):
        self.calls.append(
            roaming_appdata_path
        )
        return DETECTION_RESULT


class FakeIdentityService(
    CustomerVPSConnectMT5AccountIdentityService
):
    def __init__(self):
        self.calls = []

    def probe_binding(
        self,
        *,
        option,
    ):
        self.calls.append(option)

        return SimpleNamespace(
            identity=SimpleNamespace(
                account_fingerprint=ACCOUNT_FINGERPRINT,
            ),
            preflight_result=PREFLIGHT_RESULT,
        )


class FakeCore(
    CustomerVPSConnectCoreOrchestrationService
):
    def __init__(self):
        self.prepare_calls = []

    def prepare(
        self,
        *,
        activation_code,
        account_fingerprint,
    ):
        self.prepare_calls.append(
            (
                activation_code,
                account_fingerprint,
            )
        )

        return CustomerVPSConnectCoreOrchestrationResult(
            status="grant_ready",
            expires_at="2026-09-11T00:00:00+00:00",
        )


class FakeAgentVerifier(
    CustomerVPSConnectMT5InstalledAgentVerifier
):
    def __init__(self):
        self.calls = []

    def verify(
        self,
        *,
        preflight_result,
    ):
        self.calls.append(
            preflight_result
        )

        return SimpleNamespace(
            terminal_path=TERMINAL_PATH,
            data_path=DATA_PATH,
            account_fingerprint=ACCOUNT_FINGERPRINT,
            installed_path=INSTALLED_PATH,
        )


class FakeSymbolDiscovery(
    CustomerVPSConnectMT5SymbolDiscoveryService
):
    def __init__(self):
        self.calls = []

    def discover(
        self,
        *,
        preflight_result,
    ):
        self.calls.append(
            preflight_result
        )

        return (
            "EURUSD",
            "XAUUSD.a",
            "GOLD",
        )


class FakeRuntimePreparation(
    CustomerVPSConnectMT5RuntimePreparationService
):
    def __init__(self):
        self.prepare_calls = []
        self.gold_calls = []
        self.plan_calls = []
        self.render_calls = []

    def prepare(
        self,
        *,
        preflight_result,
        installation_result,
    ):
        self.prepare_calls.append(
            (
                preflight_result,
                installation_result,
            )
        )

        return SimpleNamespace(
            terminal_path=TERMINAL_PATH,
            data_path=DATA_PATH,
            account_fingerprint=ACCOUNT_FINGERPRINT,
            installed_path=INSTALLED_PATH,
        )

    def select_gold_symbol(
        self,
        *,
        symbols,
    ):
        self.gold_calls.append(symbols)
        return "XAUUSD.a"

    def build_startup_plan(
        self,
        *,
        preparation_result,
        symbol,
    ):
        self.plan_calls.append(
            (
                preparation_result,
                symbol,
            )
        )

        return SimpleNamespace(
            terminal_path=TERMINAL_PATH,
            symbol=symbol,
        )

    def render_startup_config(
        self,
        *,
        startup_plan,
    ):
        self.render_calls.append(
            startup_plan
        )

        return (
            "[StartUp]\n"
            "Expert=TODOBA_Trusted_Agent\n"
            "Symbol=XAUUSD.a\n"
            "Period=H1\n"
        )


class FakeStartupConfigService(
    CustomerVPSConnectMT5StartupConfigService
):
    def __init__(self):
        self.calls = []

    def write(
        self,
        *,
        directory,
        config_text,
    ):
        self.calls.append(
            (
                directory,
                config_text,
            )
        )

        return SimpleNamespace(
            config_path=CONFIG_PATH,
        )


class FakeMT5Launcher(
    CustomerVPSConnectMT5LauncherService
):
    def __init__(self):
        self.calls = []

    def launch(
        self,
        *,
        terminal_path,
        config_path,
    ):
        self.calls.append(
            (
                terminal_path,
                config_path,
            )
        )

        return SimpleNamespace(
            process_id=4321,
            terminal_path=terminal_path,
            config_path=config_path,
        )


def _shell():
    detection = FakeDetectionService()
    identity = FakeIdentityService()
    core = FakeCore()
    verifier = FakeAgentVerifier()
    symbols = FakeSymbolDiscovery()
    runtime = FakeRuntimePreparation()
    config = FakeStartupConfigService()
    launcher = FakeMT5Launcher()

    shell = CustomerVPSConnectApplicationShell(
        detection_service=detection,
        account_identity_service=identity,
        core_service=core,
        installed_agent_verifier=verifier,
        symbol_discovery_service=symbols,
        runtime_preparation_service=runtime,
        startup_config_service=config,
        mt5_launcher_service=launcher,
        startup_config_directory=CONFIG_DIRECTORY,
    )

    return (
        shell,
        detection,
        identity,
        core,
        verifier,
        symbols,
        runtime,
        config,
        launcher,
    )


def test_connect_composes_authoritative_auto_runtime_chain():
    (
        shell,
        _,
        identity,
        core,
        verifier,
        symbols,
        runtime,
        config,
        launcher,
    ) = _shell()

    shell.open()
    shell.detect(
        roaming_appdata_path=ROAMING,
    )

    result = shell.connect(
        activation_code=ACTIVATION_CODE,
        option=OPTION,
    )

    assert result.status == "grant_ready"

    assert identity.calls == [
        OPTION,
    ]

    assert core.prepare_calls == [
        (
            ACTIVATION_CODE,
            ACCOUNT_FINGERPRINT,
        )
    ]

    assert verifier.calls == [
        PREFLIGHT_RESULT,
    ]

    assert symbols.calls == [
        PREFLIGHT_RESULT,
    ]

    assert len(
        runtime.prepare_calls
    ) == 1

    assert runtime.prepare_calls[0][0] is PREFLIGHT_RESULT

    installation_result = (
        runtime.prepare_calls[0][1]
    )

    assert (
        installation_result.installed_path
        == INSTALLED_PATH
    )

    assert runtime.gold_calls == [
        (
            "EURUSD",
            "XAUUSD.a",
            "GOLD",
        )
    ]

    assert len(
        runtime.plan_calls
    ) == 1

    assert runtime.plan_calls[0][1] == "XAUUSD.a"

    assert len(
        runtime.render_calls
    ) == 1

    assert len(
        config.calls
    ) == 1

    assert (
        config.calls[0][0]
        == CONFIG_DIRECTORY
    )

    assert launcher.calls == [
        (
            TERMINAL_PATH,
            CONFIG_PATH,
        )
    ]


def test_runtime_failure_does_not_mark_application_connected():
    (
        shell,
        _,
        _,
        _,
        verifier,
        _,
        _,
        _,
        launcher,
    ) = _shell()

    def fail_verify(
        *,
        preflight_result,
    ):
        raise RuntimeError(
            "Agent verification failed."
        )

    verifier.verify = fail_verify

    shell.open()
    shell.detect(
        roaming_appdata_path=ROAMING,
    )

    with pytest.raises(
        RuntimeError,
        match="Agent verification failed",
    ):
        shell.connect(
            activation_code=ACTIVATION_CODE,
            option=OPTION,
        )

    assert launcher.calls == []

    with pytest.raises(
        RuntimeError,
        match="connected",
    ):
        shell.verify()


def test_application_shell_still_has_no_direct_process_or_filesystem_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_application_shell.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "subprocess",
        "Popen",
        "write_text",
        "write_bytes",
        "os.system",
        "common.ini",
        "WebRequestUrl",
        "terminate(",
        "kill(",
    ):
        assert forbidden not in source
