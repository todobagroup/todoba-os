from pathlib import Path
import pytest

from backend.commercial.customer_vps_connect_core_orchestration_service import (
    CustomerVPSConnectCoreFinishReadinessResult,
    CustomerVPSConnectCoreLiveProofResult,
    CustomerVPSConnectCoreOrchestrationService,
)


def test_live_proof_contract_accepts_runtime_ready():
    result = CustomerVPSConnectCoreLiveProofResult(
        status="runtime_ready",
    )

    assert result.status == "runtime_ready"


def test_runtime_ready_never_unlocks_finish():
    service = object.__new__(
        CustomerVPSConnectCoreOrchestrationService
    )

    service._last_live_proof_status = (
        "runtime_ready"
    )

    result = service.finish_readiness()

    assert isinstance(
        result,
        CustomerVPSConnectCoreFinishReadinessResult,
    )

    assert (
        result.status
        == "finish_blocked"
    )


def test_only_vps_online_unlocks_finish():
    service = object.__new__(
        CustomerVPSConnectCoreOrchestrationService
    )

    service._last_live_proof_status = (
        "vps_online"
    )

    result = service.finish_readiness()

    assert (
        result.status
        == "finish_ready"
    )


def test_application_finish_uses_core_readiness_not_raw_vps_status():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_application_shell.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert "finish_readiness" in source
    assert '"finish_ready"' in source


def test_auto2_must_not_mutate_metaquotes_global_configuration():
    owners = (
        Path(
            "backend/commercial/"
            "customer_vps_connect_application_shell.py"
        ),
        Path(
            "backend/commercial/"
            "customer_vps_connect_launcher.py"
        ),
    )

    for path in owners:
        source = path.read_text(
            encoding="utf-8-sig"
        )

        for forbidden in (
            "common.ini",
            "WebRequestUrl",
            "pywinauto",
            "uiautomation",
        ):
            assert forbidden not in source
