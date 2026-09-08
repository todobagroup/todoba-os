from pathlib import Path

import pytest

import scripts.customer_vps_connect as entrypoint


CLOUD_BASE_URL = "https://api.todobagroup.com"
APPDATA = r"C:\Users\Customer\AppData\Roaming"


class FakeLauncher:
    instances = []

    def __init__(
        self,
        *,
        cloud_base_url,
        roaming_appdata_path,
        mt5_module,
    ):
        self.cloud_base_url = cloud_base_url
        self.roaming_appdata_path = roaming_appdata_path
        self.mt5_module = mt5_module
        self.run_calls = 0

        type(self).instances.append(self)

    def run(self):
        self.run_calls += 1


def test_resolve_roaming_appdata_from_windows_environment(
    monkeypatch,
):
    monkeypatch.setenv(
        "APPDATA",
        APPDATA,
    )

    result = (
        entrypoint._resolve_roaming_appdata_path()
    )

    assert result == Path(APPDATA)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "   ",
    ],
)
def test_invalid_windows_appdata_fails_closed(
    monkeypatch,
    value,
):
    if value is None:
        monkeypatch.delenv(
            "APPDATA",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "APPDATA",
            value,
        )

    with pytest.raises(RuntimeError):
        entrypoint._resolve_roaming_appdata_path()


def test_production_entrypoint_composes_and_runs_launcher(
    monkeypatch,
):
    FakeLauncher.instances = []

    fake_mt5 = object()

    monkeypatch.setattr(
        entrypoint,
        "CustomerVPSConnectLauncher",
        FakeLauncher,
    )

    monkeypatch.setattr(
        entrypoint,
        "TODOBA_CLOUD_BASE_URL",
        CLOUD_BASE_URL,
    )

    monkeypatch.setattr(
        entrypoint,
        "mt5",
        fake_mt5,
    )

    monkeypatch.setenv(
        "APPDATA",
        APPDATA,
    )

    result = (
        entrypoint.run_production_customer_vps_connect()
    )

    assert result is None
    assert len(FakeLauncher.instances) == 1

    launcher = FakeLauncher.instances[0]

    assert launcher.cloud_base_url == CLOUD_BASE_URL

    assert (
        launcher.roaming_appdata_path
        == Path(APPDATA)
    )

    assert launcher.mt5_module is fake_mt5
    assert launcher.run_calls == 1


def test_main_returns_zero_on_success(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        entrypoint,
        "run_production_customer_vps_connect",
        lambda: calls.append("run"),
    )

    assert entrypoint.main() == 0
    assert calls == ["run"]


def test_main_failure_is_customer_safe_and_does_not_leak_exception(
    monkeypatch,
):
    secret = "internal-secret-c7d1"

    def fail():
        raise RuntimeError(secret)

    shown = []

    monkeypatch.setattr(
        entrypoint,
        "run_production_customer_vps_connect",
        fail,
    )

    monkeypatch.setattr(
        entrypoint.messagebox,
        "showerror",
        lambda title, message: shown.append(
            (title, message)
        ),
    )

    assert entrypoint.main() == 1

    assert len(shown) == 1

    title, message = shown[0]

    assert title == "TODOBA VPS Connect"
    assert secret not in message
    assert message


def test_entrypoint_has_launch_authority_only():
    source = Path(
        "scripts/customer_vps_connect.py"
    ).read_text(
        encoding="utf-8-sig",
    )

    assert (
        "CustomerVPSConnectLauncher"
        in source
    )

    assert (
        "TODOBA_CLOUD_BASE_URL"
        in source
    )

    assert (
        "import MetaTrader5 as mt5"
        in source
    )

    for forbidden in (
        "CustomerVPSConnectCoreOrchestrationService",
        "CustomerVPSConnectGrantHttpClient",
        "CustomerVPSConnectLiveProofHttpClient",
        "CustomerVPSConnectMT5DetectionService",
        "CustomerVPSConnectMT5AccountIdentityService",
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