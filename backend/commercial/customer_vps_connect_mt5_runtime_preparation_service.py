"""
TODOBA Customer VPS Connect MT5 Runtime Preparation Service.

Establishes the exact installed MT5 runtime identity that later
customer-side preparation steps are permitted to use.

This owner does not launch or mutate the selected terminal yet.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallationResult,
)

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)


_ARTIFACT_FILENAME = "TODOBA_Trusted_Agent.ex5"


@dataclass(
    frozen=True,
)
class CustomerVPSConnectMT5RuntimePreparationResult:
    """
    Bound customer-side MT5 runtime preparation evidence.
    """

    terminal_path: str
    data_path: str
    account_fingerprint: str
    installed_path: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "terminal_path",
            "data_path",
            "account_fingerprint",
            "installed_path",
        ):
            value = getattr(
                self,
                name,
            )

            if not isinstance(
                value,
                str,
            ):
                raise TypeError(
                    f"{name} must be str."
                )

            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    f"{name} is required."
                )

            object.__setattr__(
                self,
                name,
                normalized,
            )


@dataclass(
    frozen=True,
)
class CustomerVPSConnectMT5StartupPlan:
    """
    Supported startup intent bound to one verified MT5 runtime.

    The symbol supplied here must already have been validated
    against the exact selected terminal/account.
    """

    terminal_path: str
    data_path: str
    account_fingerprint: str
    installed_path: str
    expert_name: str
    symbol: str
    period: str

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "terminal_path",
            "data_path",
            "account_fingerprint",
            "installed_path",
            "expert_name",
            "symbol",
            "period",
        ):
            value = getattr(
                self,
                name,
            )

            if not isinstance(
                value,
                str,
            ):
                raise TypeError(
                    f"{name} must be str."
                )

            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    f"{name} is required."
                )

            object.__setattr__(
                self,
                name,
                normalized,
            )


class CustomerVPSConnectMT5RuntimePreparationService:
    """
    Bind one verified installation to one exact preflight identity.
    """

    def select_gold_symbol(
        self,
        *,
        symbols: tuple[str, ...],
    ) -> str:
        if not isinstance(
            symbols,
            tuple,
        ):
            raise TypeError(
                "symbols must be tuple."
            )

        if not symbols:
            raise ValueError(
                "symbols must not be empty."
            )

        normalized_symbols: list[str] = []

        for symbol in symbols:
            if not isinstance(
                symbol,
                str,
            ):
                raise TypeError(
                    "each symbol must be str."
                )

            normalized = symbol.strip()

            if not normalized:
                raise ValueError(
                    "symbol must not be empty."
                )

            if any(
                character in normalized
                for character in (
                    "\r",
                    "\n",
                    "=",
                    "[",
                    "]",
                )
            ):
                raise ValueError(
                    "symbol contains unsupported characters."
                )

            normalized_symbols.append(
                normalized
            )

        def rank(
            symbol: str,
        ) -> tuple[int, str]:
            upper = symbol.upper()

            if upper == "XAUUSD":
                return (
                    0,
                    upper,
                )

            if upper.startswith(
                "XAUUSD"
            ):
                return (
                    1,
                    upper,
                )

            if upper == "GOLD":
                return (
                    2,
                    upper,
                )

            if upper.startswith(
                "GOLD"
            ):
                return (
                    3,
                    upper,
                )

            return (
                100,
                upper,
            )

        ranked = sorted(
            normalized_symbols,
            key=rank,
        )

        selected = ranked[0]

        if rank(
            selected
        )[0] >= 100:
            raise RuntimeError(
                "No supported gold symbol is available."
            )

        return selected

    def render_startup_config(
        self,
        *,
        startup_plan: CustomerVPSConnectMT5StartupPlan,
    ) -> str:
        if not isinstance(
            startup_plan,
            CustomerVPSConnectMT5StartupPlan,
        ):
            raise TypeError(
                "startup_plan must be "
                "CustomerVPSConnectMT5StartupPlan."
            )

        return (
            "[StartUp]\n"
            f"Expert={startup_plan.expert_name}\n"
            f"Symbol={startup_plan.symbol}\n"
            f"Period={startup_plan.period}\n"
        )

    def build_startup_plan(
        self,
        *,
        preparation_result: CustomerVPSConnectMT5RuntimePreparationResult,
        symbol: str,
    ) -> CustomerVPSConnectMT5StartupPlan:
        if not isinstance(
            preparation_result,
            CustomerVPSConnectMT5RuntimePreparationResult,
        ):
            raise TypeError(
                "preparation_result must be "
                "CustomerVPSConnectMT5RuntimePreparationResult."
            )

        if not isinstance(
            symbol,
            str,
        ):
            raise TypeError(
                "symbol must be str."
            )

        normalized_symbol = symbol.strip()

        if not normalized_symbol:
            raise ValueError(
                "symbol is required."
            )

        if any(
            character in normalized_symbol
            for character in (
                "\r",
                "\n",
                "=",
                "[",
                "]",
            )
        ):
            raise ValueError(
                "symbol contains unsupported characters."
            )

        return CustomerVPSConnectMT5StartupPlan(
            terminal_path=(
                preparation_result.terminal_path
            ),
            data_path=(
                preparation_result.data_path
            ),
            account_fingerprint=(
                preparation_result.account_fingerprint
            ),
            installed_path=(
                preparation_result.installed_path
            ),
            expert_name="TODOBA_Trusted_Agent",
            symbol=normalized_symbol,
            period="H1",
        )

    def prepare(
        self,
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
        installation_result: CustomerMT5EX5InstallationResult,
    ) -> CustomerVPSConnectMT5RuntimePreparationResult:
        if not isinstance(
            preflight_result,
            CustomerMT5SetupPreflightResult,
        ):
            raise TypeError(
                "preflight_result must be "
                "CustomerMT5SetupPreflightResult."
            )

        if not isinstance(
            installation_result,
            CustomerMT5EX5InstallationResult,
        ):
            raise TypeError(
                "installation_result must be "
                "CustomerMT5EX5InstallationResult."
            )

        if (
            _windows_path_key(
                preflight_result.terminal_path
            )
            != _windows_path_key(
                installation_result.terminal_path
            )
        ):
            raise ValueError(
                "Installed terminal does not match "
                "authoritative MT5 preflight."
            )

        if (
            _windows_path_key(
                preflight_result.data_path
            )
            != _windows_path_key(
                installation_result.data_path
            )
        ):
            raise ValueError(
                "Installed data path does not match "
                "authoritative MT5 preflight."
            )

        if (
            installation_result.account_fingerprint
            != preflight_result.account_fingerprint
        ):
            raise ValueError(
                "Installed account identity does not match "
                "authoritative MT5 preflight."
            )

        expected_installed_path = (
            Path(
                preflight_result.data_path
            )
            / "MQL5"
            / "Experts"
            / _ARTIFACT_FILENAME
        )

        if (
            _windows_path_key(
                installation_result.installed_path
            )
            != _windows_path_key(
                str(
                    expected_installed_path
                )
            )
        ):
            raise ValueError(
                "Installed Agent path does not match "
                "authoritative MT5 data path."
            )

        return (
            CustomerVPSConnectMT5RuntimePreparationResult(
                terminal_path=(
                    preflight_result.terminal_path
                ),
                data_path=(
                    preflight_result.data_path
                ),
                account_fingerprint=(
                    preflight_result.account_fingerprint
                ),
                installed_path=(
                    installation_result.installed_path
                ),
            )
        )


def _windows_path_key(
    value: str,
) -> str:
    return os.path.normpath(
        value
    ).replace(
        "/",
        "\\",
    ).casefold()
