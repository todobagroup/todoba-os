"""
TODOBA VPS Connect Core Orchestration.

Owns the customer-side in-process grant session.

Responsibilities:
- accept activation code plus canonical account fingerprint
- acquire one short-lived grant through the HTTP transport
- retain the grant only in process memory
- bind the in-memory session to one account fingerprint
- expose only customer-safe readiness state

This owner has no persistence, MT5 automation, VPS automation,
GUI, deployment mutation, or server composition authority.
"""

from dataclasses import dataclass
from typing import Literal

from backend.commercial.customer_vps_connect_grant_http_client import (
    CustomerVPSConnectGrantHttpClient,
    CustomerVPSConnectGrantTransportResult,
)
from backend.commercial.customer_vps_connect_live_proof_http_client import (
    CustomerVPSConnectLiveProofHttpClient,
    CustomerVPSConnectLiveProofTransportResult,
)


def _normalize_required_string(
    value: str,
    *,
    name: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{name} must be str."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{name} is required."
        )

    return normalized


@dataclass(
    frozen=True,
)
class CustomerVPSConnectCoreOrchestrationResult:
    status: Literal["grant_ready"]
    expires_at: str

    def __post_init__(
        self,
    ) -> None:
        if self.status != "grant_ready":
            raise ValueError(
                "Unsupported VPS Connect core status."
            )

        object.__setattr__(
            self,
            "expires_at",
            _normalize_required_string(
                self.expires_at,
                name="expires_at",
            ),
        )


@dataclass(
    frozen=True,
)
class CustomerVPSConnectCoreLiveProofResult:
    status: Literal[
        "vps_pending",
        "vps_online",
    ]

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.status,
            str,
        ):
            raise TypeError(
                "status must be str."
            )

        if self.status not in {
            "vps_pending",
            "vps_online",
        }:
            raise ValueError(
                "Unsupported VPS Connect "
                "live proof status."
            )


class CustomerVPSConnectCoreOrchestrationService:
    """
    Hold one customer VPS Connect grant session in memory.
    """

    def __init__(
        self,
        *,
        grant_http_client: CustomerVPSConnectGrantHttpClient,
        live_proof_http_client: CustomerVPSConnectLiveProofHttpClient | None = None,
    ) -> None:
        if not isinstance(
            grant_http_client,
            CustomerVPSConnectGrantHttpClient,
        ):
            raise TypeError(
                "grant_http_client must be "
                "CustomerVPSConnectGrantHttpClient."
            )

        if (
            live_proof_http_client is not None
            and not isinstance(
                live_proof_http_client,
                CustomerVPSConnectLiveProofHttpClient,
            )
        ):
            raise TypeError(
                "live_proof_http_client must be "
                "CustomerVPSConnectLiveProofHttpClient "
                "or None."
            )

        self._grant_http_client = grant_http_client
        self._live_proof_http_client = (
            live_proof_http_client
        )

        self._grant_credential: str | None = None
        self._grant_expires_at: str | None = None
        self._account_fingerprint: str | None = None

    def __repr__(
        self,
    ) -> str:
        state = (
            "grant_ready"
            if self._grant_credential is not None
            else "empty"
        )

        return (
            "CustomerVPSConnectCoreOrchestrationService("
            f"state={state!r})"
        )

    def prepare(
        self,
        *,
        activation_code: str,
        account_fingerprint: str,
    ) -> CustomerVPSConnectCoreOrchestrationResult:
        normalized_activation_code = (
            _normalize_required_string(
                activation_code,
                name="activation_code",
            )
        )

        normalized_account_fingerprint = (
            _normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        if self._grant_credential is not None:
            if (
                self._account_fingerprint
                != normalized_account_fingerprint
            ):
                raise RuntimeError(
                    "VPS Connect account identity "
                    "changed during active grant session."
                )

            if self._grant_expires_at is None:
                raise RuntimeError(
                    "VPS Connect in-memory grant "
                    "state is inconsistent."
                )

            return (
                CustomerVPSConnectCoreOrchestrationResult(
                    status="grant_ready",
                    expires_at=self._grant_expires_at,
                )
            )

        transport_result = (
            self._grant_http_client.issue(
                activation_code=(
                    normalized_activation_code
                ),
                account_fingerprint=(
                    normalized_account_fingerprint
                ),
            )
        )

        if not isinstance(
            transport_result,
            CustomerVPSConnectGrantTransportResult,
        ):
            raise RuntimeError(
                "VPS Connect grant transport "
                "returned invalid result."
            )

        self._grant_credential = (
            transport_result.grant_credential
        )
        self._grant_expires_at = (
            transport_result.expires_at
        )
        self._account_fingerprint = (
            normalized_account_fingerprint
        )

        return (
            CustomerVPSConnectCoreOrchestrationResult(
                status="grant_ready",
                expires_at=(
                    transport_result.expires_at
                ),
            )
        )

    def check_live_proof(
        self,
    ) -> CustomerVPSConnectCoreLiveProofResult:
        if self._grant_credential is None:
            raise RuntimeError(
                "VPS Connect grant is not ready."
            )

        if self._live_proof_http_client is None:
            raise RuntimeError(
                "VPS Connect live proof transport "
                "is unavailable."
            )

        transport_result = (
            self._live_proof_http_client.verify(
                grant_credential=(
                    self._grant_credential
                ),
            )
        )

        if not isinstance(
            transport_result,
            CustomerVPSConnectLiveProofTransportResult,
        ):
            raise RuntimeError(
                "VPS Connect live proof transport "
                "returned invalid result."
            )

        return CustomerVPSConnectCoreLiveProofResult(
            status=transport_result.status,
        )
