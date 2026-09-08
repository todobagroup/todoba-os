"""
TODOBA VPS Connect MT5 Account Identity.

Projects the authoritative result of the existing selected-terminal
MT5 preflight into a VPS Connect customer-safe account identity.

The existing CustomerMT5SetupPreflightService remains the sole owner
of MT5 initialization and hedging-account validation.

This owner:
- accepts one customer-selected detection option
- delegates the exact terminal probe to the existing preflight owner
- verifies selected-terminal identity convergence
- verifies the canonical server:login account fingerprint
- exposes only customer-safe account identity

It has no grant, persistence, VPS automation, password, or commercial
state mutation authority.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
    CustomerMT5SetupPreflightService,
)

from backend.commercial.customer_vps_connect_mt5_detection_service import (
    CustomerVPSConnectMT5DetectionOption,
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
class CustomerVPSConnectMT5AccountIdentityResult:
    status: Literal["account_ready"]
    terminal_path: str
    login: int
    server: str
    account_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        if self.status != "account_ready":
            raise ValueError(
                "Unsupported VPS Connect account identity status."
            )

        object.__setattr__(
            self,
            "terminal_path",
            _normalize_required_string(
                self.terminal_path,
                name="terminal_path",
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

        object.__setattr__(
            self,
            "server",
            _normalize_required_string(
                self.server,
                name="server",
            ),
        )

        object.__setattr__(
            self,
            "account_fingerprint",
            _normalize_required_string(
                self.account_fingerprint,
                name="account_fingerprint",
            ),
        )


class CustomerVPSConnectMT5AccountIdentityService:
    """
    Probe one selected MT5 installation through the existing
    authoritative MT5 preflight owner.
    """

    def __init__(
        self,
        *,
        mt5_preflight_service: CustomerMT5SetupPreflightService,
    ) -> None:
        if not isinstance(
            mt5_preflight_service,
            CustomerMT5SetupPreflightService,
        ):
            raise TypeError(
                "mt5_preflight_service must be "
                "CustomerMT5SetupPreflightService."
            )

        self._mt5_preflight_service = (
            mt5_preflight_service
        )

    def probe(
        self,
        *,
        option: CustomerVPSConnectMT5DetectionOption,
    ) -> CustomerVPSConnectMT5AccountIdentityResult:
        if not isinstance(
            option,
            CustomerVPSConnectMT5DetectionOption,
        ):
            raise TypeError(
                "option must be "
                "CustomerVPSConnectMT5DetectionOption."
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
                "MT5 preflight returned invalid account identity."
            )

        if (
            preflight_result.terminal_path
            != option.terminal_path
        ):
            raise RuntimeError(
                "Selected MT5 terminal identity does not converge."
            )

        if (
            preflight_result.installation_path
            != option.installation_path
        ):
            raise RuntimeError(
                "Selected MT5 installation identity does not converge."
            )

        if (
            preflight_result.portable
            != option.portable
        ):
            raise RuntimeError(
                "Selected MT5 portable identity does not converge."
            )

        canonical_account_fingerprint = (
            f"{preflight_result.server}:"
            f"{preflight_result.login}"
        )

        if (
            preflight_result.account_fingerprint
            != canonical_account_fingerprint
        ):
            raise RuntimeError(
                "MT5 account fingerprint is not canonical."
            )

        return (
            CustomerVPSConnectMT5AccountIdentityResult(
                status="account_ready",
                terminal_path=(
                    preflight_result.terminal_path
                ),
                login=(
                    preflight_result.login
                ),
                server=(
                    preflight_result.server
                ),
                account_fingerprint=(
                    preflight_result.account_fingerprint
                ),
            )
        )
