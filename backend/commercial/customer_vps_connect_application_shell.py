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

        self._detection_service = detection_service
        self._account_identity_service = (
            account_identity_service
        )
        self._core_service = core_service

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