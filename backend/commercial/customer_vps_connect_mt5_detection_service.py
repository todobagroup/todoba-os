"""
TODOBA VPS Connect MT5 Detection.

Projects the existing standard MetaTrader installation
discovery into a small customer-safe result.

This owner delegates all filesystem discovery to the
existing MT5 preflight owner. It does not probe an
account, initialize a terminal, persist state, automate
VPS operations, or mutate commercial setup state.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5InstallationCandidate,
    CustomerMT5SetupPreflightService,
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
class CustomerVPSConnectMT5DetectionOption:
    installation_path: str
    terminal_path: str
    portable: bool

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "installation_path",
            _normalize_required_string(
                self.installation_path,
                name="installation_path",
            ),
        )

        object.__setattr__(
            self,
            "terminal_path",
            _normalize_required_string(
                self.terminal_path,
                name="terminal_path",
            ),
        )

        if not isinstance(
            self.portable,
            bool,
        ):
            raise TypeError(
                "portable must be bool."
            )


@dataclass(
    frozen=True,
)
class CustomerVPSConnectMT5DetectionResult:
    status: Literal[
        "detected",
        "not_found",
    ]
    installations: tuple[
        CustomerVPSConnectMT5DetectionOption,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:
        if self.status not in {
            "detected",
            "not_found",
        }:
            raise ValueError(
                "Unsupported MT5 detection status."
            )

        if not isinstance(
            self.installations,
            tuple,
        ):
            raise TypeError(
                "installations must be tuple."
            )

        for item in self.installations:
            if not isinstance(
                item,
                CustomerVPSConnectMT5DetectionOption,
            ):
                raise TypeError(
                    "installations contains invalid item."
                )

        if (
            self.status == "detected"
            and not self.installations
        ):
            raise ValueError(
                "detected requires at least one installation."
            )

        if (
            self.status == "not_found"
            and self.installations
        ):
            raise ValueError(
                "not_found must not contain installations."
            )


class CustomerVPSConnectMT5DetectionService:
    """
    Customer-safe projection over standard MT5 discovery.
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

    def detect(
        self,
        *,
        roaming_appdata_path: Path,
    ) -> CustomerVPSConnectMT5DetectionResult:
        if not isinstance(
            roaming_appdata_path,
            Path,
        ):
            raise TypeError(
                "roaming_appdata_path must be Path."
            )

        discovered = (
            self._mt5_preflight_service
            .discover_standard_installations(
                roaming_appdata_path=(
                    roaming_appdata_path
                ),
            )
        )

        if not isinstance(
            discovered,
            tuple,
        ):
            raise RuntimeError(
                "MT5 discovery returned invalid result."
            )

        projected = []

        for candidate in discovered:
            if not isinstance(
                candidate,
                CustomerMT5InstallationCandidate,
            ):
                raise RuntimeError(
                    "MT5 discovery returned invalid candidate."
                )

            projected.append(
                CustomerVPSConnectMT5DetectionOption(
                    installation_path=(
                        candidate.installation_path
                    ),
                    terminal_path=(
                        candidate.terminal_path
                    ),
                    portable=(
                        candidate.portable
                    ),
                )
            )

        installations = tuple(
            projected
        )

        if not installations:
            return (
                CustomerVPSConnectMT5DetectionResult(
                    status="not_found",
                    installations=(),
                )
            )

        return (
            CustomerVPSConnectMT5DetectionResult(
                status="detected",
                installations=installations,
            )
        )
