from pathlib import Path

import pytest

import backend.commercial.customer_vps_connect_launcher as launcher_module

from backend.commercial.customer_vps_connect_launcher import (
    CustomerVPSConnectLauncher,
)


CLOUD_BASE_URL = "https://api.todobagroup.com"
ROAMING = Path(
    r"C:\Users\Customer\AppData\Roaming"
)
MT5_MODULE = object()


class FakePreflight:
    instances = []

    def __init__(
        self,
        *,
        mt5_module,
    ):
        self.mt5_module = mt5_module
        type(self).instances.append(self)


class FakeDetection:
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


class FakeIdentity:
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


class FakeGrantClient:
    instances = []

    def __init__(
        self,
        *,
        cloud_base_url,
    ):
        self.cloud_base_url = cloud_base_url
        type(self).instances.append(self)


class FakeLiveProofClient:
    instances = []

    def __init__(
        self,
        *,
        cloud_base_url,
    ):
        self.cloud_base_url = cloud_base_url
        type(self).instances.append(self)


class FakeCore:
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


class FakeApplicationShell:
    instances = []

    def __init__(
        self,
        *,
        detection_service,
        account_identity_service,
        core_service,
    ):
        self.detection_service = (
            detection_service
        )
        self.account_identity_service = (
            account_identity_service
        )
        self.core_service = core_service
        type(self).instances.append(self)


class FakeGuiShell:
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
        self.run_calls = 0
        type(self).instances.append(self)

    def run(self):
        self.run_calls += 1


def _reset():
    for owner in (
        FakePreflight,
        FakeDetection,
        FakeIdentity,
        FakeGrantClient,
        FakeLiveProofClient,
        FakeCore,
        FakeApplicationShell,
        FakeGuiShell,
    ):
        owner.instances = []


def _patch(monkeypatch):
    _reset()

    monkeypatch.setattr(
        launcher_module,
        "CustomerMT5SetupPreflightService",
        FakePreflight,
    )

    monkeypatch.setattr(
        launcher_module,
        "CustomerVPSConnectMT5DetectionService",
        FakeDetection,
    )

    monkeypatch.setattr(
        launcher_module,
        "CustomerVPSConnectMT5AccountIdentityService",
        FakeIdentity,
    )

    monkeypatch.setattr(
        launcher_module,
        "CustomerVPSConnectGrantHttpClient",
        FakeGrantClient,
    )

    monkeypatch.setattr(
        launcher_module,
        "CustomerVPSConnectLiveProofHttpClient",
        FakeLiveProofClient,
    )

    monkeypatch.setattr(
        launcher_module,
        "CustomerVPSConnectCoreOrchestrationService",
        FakeCore,
    )

    monkeypatch.setattr(
        launcher_module,
        "CustomerVPSConnectApplicationShell",
        FakeApplicationShell,
    )

    monkeypatch.setattr(
        launcher_module,
        "CustomerVPSConnectGuiShell",
        FakeGuiShell,
    )


def _launcher(monkeypatch):
    _patch(monkeypatch)

    return CustomerVPSConnectLauncher(
        cloud_base_url=CLOUD_BASE_URL,
        roaming_appdata_path=ROAMING,
        mt5_module=MT5_MODULE,
    )


def test_launcher_constructs_exactly_one_shared_mt5_preflight(
    monkeypatch,
):
    _launcher(monkeypatch)

    assert len(FakePreflight.instances) == 1
    assert len(FakeDetection.instances) == 1
    assert len(FakeIdentity.instances) == 1

    preflight = FakePreflight.instances[0]

    assert preflight.mt5_module is MT5_MODULE

    assert (
        FakeDetection.instances[0]
        .mt5_preflight_service
        is preflight
    )

    assert (
        FakeIdentity.instances[0]
        .mt5_preflight_service
        is preflight
    )


def test_launcher_constructs_both_http_clients_from_same_cloud_boundary(
    monkeypatch,
):
    _launcher(monkeypatch)

    assert len(
        FakeGrantClient.instances
    ) == 1

    assert len(
        FakeLiveProofClient.instances
    ) == 1

    assert (
        FakeGrantClient.instances[0]
        .cloud_base_url
        == CLOUD_BASE_URL
    )

    assert (
        FakeLiveProofClient.instances[0]
        .cloud_base_url
        == CLOUD_BASE_URL
    )


def test_launcher_composes_core_with_existing_transport_owners(
    monkeypatch,
):
    _launcher(monkeypatch)

    assert len(FakeCore.instances) == 1

    core = FakeCore.instances[0]

    assert (
        core.grant_http_client
        is FakeGrantClient.instances[0]
    )

    assert (
        core.live_proof_http_client
        is FakeLiveProofClient.instances[0]
    )


def test_launcher_composes_application_shell_from_existing_owners(
    monkeypatch,
):
    _launcher(monkeypatch)

    assert len(
        FakeApplicationShell.instances
    ) == 1

    application = (
        FakeApplicationShell.instances[0]
    )

    assert (
        application.detection_service
        is FakeDetection.instances[0]
    )

    assert (
        application.account_identity_service
        is FakeIdentity.instances[0]
    )

    assert (
        application.core_service
        is FakeCore.instances[0]
    )


def test_launcher_composes_gui_with_application_and_roaming_path(
    monkeypatch,
):
    launcher = _launcher(monkeypatch)

    assert len(
        FakeGuiShell.instances
    ) == 1

    gui = FakeGuiShell.instances[0]

    assert (
        gui.application_shell
        is FakeApplicationShell.instances[0]
    )

    assert (
        gui.roaming_appdata_path
        == ROAMING
    )

    assert launcher._gui_shell is gui


def test_run_delegates_exactly_once_to_gui(
    monkeypatch,
):
    launcher = _launcher(monkeypatch)

    gui = FakeGuiShell.instances[0]

    launcher.run()

    assert gui.run_calls == 1


def test_launcher_has_composition_authority_only():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_launcher.py"
    ).read_text(
        encoding="utf-8-sig",
    )

    for forbidden in (
        "customer_setup_gui_shell",
        "CustomerVPSConnectGrantService",
        "CustomerVPSConnectLiveProofService",
        "BrokerStateStore",
        "initialize_empty",
        "write_text",
        "write_bytes",
        "PyInstaller",
        "subprocess",
        "terminate(",
        "kill(",
        "time.sleep",
        "threading",
        "while True",
        "common.ini",
        "WebRequestUrl",
    ):
        assert forbidden not in source