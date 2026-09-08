from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.commercial.customer_vps_connect_application_shell import (
    CustomerVPSConnectApplicationShell,
)

from backend.commercial.customer_vps_connect_core_orchestration_service import (
    CustomerVPSConnectCoreFinishReadinessResult,
    CustomerVPSConnectCoreLiveProofResult,
    CustomerVPSConnectCoreOrchestrationResult,
    CustomerVPSConnectCoreOrchestrationService,
)

from backend.commercial.customer_vps_connect_mt5_account_identity_service import (
    CustomerVPSConnectMT5AccountIdentityService,
)

from backend.commercial.customer_vps_connect_mt5_detection_service import (
    CustomerVPSConnectMT5DetectionService,
)


ROAMING = Path(r"C:\Users\Customer\AppData\Roaming")
ACTIVATION_CODE = "setup-activation-c7a-secret"
ACCOUNT_FINGERPRINT = "Broker-Pro:12345678"
EXPIRES_AT = "2026-09-08T16:00:00+00:00"

OPTION = object()
DETECTION_RESULT = object()


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

    def probe(
        self,
        *,
        option,
    ):
        self.calls.append(option)

        return SimpleNamespace(
            account_fingerprint=ACCOUNT_FINGERPRINT,
        )


class FakeCore(
    CustomerVPSConnectCoreOrchestrationService
):
    def __init__(
        self,
        *,
        proof_statuses=None,
    ):
        self.prepare_calls = []
        self.proof_statuses = list(
            proof_statuses or []
        )
        self.finish_status = "finish_blocked"

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
            expires_at=EXPIRES_AT,
        )

    def check_live_proof(self):
        status = self.proof_statuses.pop(0)

        self.finish_status = (
            "finish_ready"
            if status == "vps_online"
            else "finish_blocked"
        )

        return CustomerVPSConnectCoreLiveProofResult(
            status=status,
        )

    def finish_readiness(self):
        return CustomerVPSConnectCoreFinishReadinessResult(
            status=self.finish_status,
        )


def _shell(
    *,
    proof_statuses=None,
):
    detection = FakeDetectionService()
    identity = FakeIdentityService()
    core = FakeCore(
        proof_statuses=proof_statuses,
    )

    shell = CustomerVPSConnectApplicationShell(
        detection_service=detection,
        account_identity_service=identity,
        core_service=core,
    )

    return shell, detection, identity, core


def test_detect_requires_open():
    shell, detection, _, _ = _shell()

    with pytest.raises(RuntimeError):
        shell.detect(
            roaming_appdata_path=ROAMING,
        )

    assert detection.calls == []


def test_open_then_detect_calls_existing_detection_owner():
    shell, detection, _, _ = _shell()

    assert shell.open() is None

    result = shell.detect(
        roaming_appdata_path=ROAMING,
    )

    assert result is DETECTION_RESULT
    assert detection.calls == [ROAMING]


def test_connect_requires_detection():
    shell, _, identity, core = _shell()

    shell.open()

    with pytest.raises(RuntimeError):
        shell.connect(
            activation_code=ACTIVATION_CODE,
            option=OPTION,
        )

    assert identity.calls == []
    assert core.prepare_calls == []


def test_connect_probes_selected_account_then_prepares_core():
    shell, _, identity, core = _shell()

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


def test_shell_does_not_retain_activation_or_account_authority():
    shell, _, _, _ = _shell()

    shell.open()
    shell.detect(
        roaming_appdata_path=ROAMING,
    )

    shell.connect(
        activation_code=ACTIVATION_CODE,
        option=OPTION,
    )

    representation = repr(shell)

    assert ACTIVATION_CODE not in representation
    assert ACCOUNT_FINGERPRINT not in representation

    for value in vars(shell).values():
        assert value != ACTIVATION_CODE
        assert value != ACCOUNT_FINGERPRINT


def test_verify_requires_connect():
    shell, _, _, _ = _shell(
        proof_statuses=[
            "vps_online",
        ]
    )

    shell.open()
    shell.detect(
        roaming_appdata_path=ROAMING,
    )

    with pytest.raises(RuntimeError):
        shell.verify()


@pytest.mark.parametrize(
    "status",
    [
        "vps_pending",
        "vps_online",
    ],
)
def test_verify_returns_core_live_proof(
    status,
):
    shell, _, _, _ = _shell(
        proof_statuses=[
            status,
        ]
    )

    shell.open()
    shell.detect(
        roaming_appdata_path=ROAMING,
    )
    shell.connect(
        activation_code=ACTIVATION_CODE,
        option=OPTION,
    )

    result = shell.verify()

    assert result.status == status


def test_finish_is_blocked_without_server_backed_online():
    shell, _, _, _ = _shell(
        proof_statuses=[
            "vps_pending",
        ]
    )

    shell.open()
    shell.detect(
        roaming_appdata_path=ROAMING,
    )
    shell.connect(
        activation_code=ACTIVATION_CODE,
        option=OPTION,
    )
    shell.verify()

    with pytest.raises(RuntimeError):
        shell.finish()


def test_finish_succeeds_only_after_vps_online():
    shell, _, _, _ = _shell(
        proof_statuses=[
            "vps_online",
        ]
    )

    shell.open()
    shell.detect(
        roaming_appdata_path=ROAMING,
    )
    shell.connect(
        activation_code=ACTIVATION_CODE,
        option=OPTION,
    )

    assert shell.verify().status == "vps_online"
    assert shell.finish() is None


def test_latest_pending_reblocks_finish():
    shell, _, _, _ = _shell(
        proof_statuses=[
            "vps_online",
            "vps_pending",
        ]
    )

    shell.open()
    shell.detect(
        roaming_appdata_path=ROAMING,
    )
    shell.connect(
        activation_code=ACTIVATION_CODE,
        option=OPTION,
    )

    assert shell.verify().status == "vps_online"
    assert shell.verify().status == "vps_pending"

    with pytest.raises(RuntimeError):
        shell.finish()


def test_application_shell_has_no_gui_packaging_or_persistence_authority():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_application_shell.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    for forbidden in (
        "tkinter",
        "ttk.",
        "PyInstaller",
        "subprocess",
        "write_text",
        "write_bytes",
        "initialize_empty",
        "BrokerStateStore",
        "MetaTrader5",
        "common.ini",
        "WebRequestUrl",
        "pywinauto",
        "uiautomation",
        "time.sleep",
        "threading",
        "while True",
    ):
        assert forbidden not in source