"""
TODOBA Customer VPS Connect MT5 Symbol Discovery Service.

Reads available symbols from exactly one previously preflighted
customer terminal and re-validates its identity before returning
broker-provided symbol names.

This owner is read-only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)


class CustomerVPSConnectMT5SymbolDiscoveryService:
    """
    Read symbols only from the exact preflight-bound terminal/account.
    """

    def __init__(
        self,
        *,
        mt5_module: Any,
    ) -> None:
        if mt5_module is None:
            raise TypeError(
                "mt5_module is required."
            )

        for function_name in (
            "initialize",
            "shutdown",
            "terminal_info",
            "account_info",
            "symbols_get",
        ):
            if not callable(
                getattr(
                    mt5_module,
                    function_name,
                    None,
                )
            ):
                raise TypeError(
                    "mt5_module must provide callable "
                    f"{function_name}()."
                )

        self._mt5 = mt5_module

    def discover(
        self,
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
    ) -> tuple[str, ...]:
        if not isinstance(
            preflight_result,
            CustomerMT5SetupPreflightResult,
        ):
            raise TypeError(
                "preflight_result must be "
                "CustomerMT5SetupPreflightResult."
            )

        initialize_attempted = False

        try:
            initialize_attempted = True

            initialized = bool(
                self._mt5.initialize(
                    preflight_result.terminal_path,
                    portable=preflight_result.portable,
                )
            )

            if not initialized:
                raise RuntimeError(
                    "Unable to initialize exact customer terminal."
                )

            terminal_info = self._mt5.terminal_info()

            if terminal_info is None:
                raise RuntimeError(
                    "Unable to verify customer terminal."
                )

            self._verify_terminal_identity(
                preflight_result=preflight_result,
                terminal_info=terminal_info,
            )

            account_info = self._mt5.account_info()

            if account_info is None:
                raise RuntimeError(
                    "Unable to verify customer account."
                )

            self._verify_account_identity(
                preflight_result=preflight_result,
                account_info=account_info,
            )

            raw_symbols = self._mt5.symbols_get()

            if not raw_symbols:
                raise RuntimeError(
                    "No broker symbol is available."
                )

            symbols: list[str] = []

            for item in raw_symbols:
                name = getattr(
                    item,
                    "name",
                    None,
                )

                if not isinstance(
                    name,
                    str,
                ):
                    raise RuntimeError(
                        "Broker symbol name is invalid."
                    )

                normalized = name.strip()

                if not normalized:
                    raise RuntimeError(
                        "Broker symbol name is empty."
                    )

                symbols.append(
                    normalized
                )

            if not symbols:
                raise RuntimeError(
                    "No broker symbol is available."
                )

            return tuple(
                symbols
            )

        finally:
            if initialize_attempted:
                self._mt5.shutdown()

    @staticmethod
    def _verify_terminal_identity(
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
        terminal_info: Any,
    ) -> None:
        reported_path = getattr(
            terminal_info,
            "path",
            None,
        )

        if not isinstance(
            reported_path,
            str,
        ):
            raise RuntimeError(
                "Reported terminal path is invalid."
            )

        if (
            _windows_path_key(
                reported_path
            )
            != _windows_path_key(
                preflight_result.installation_path
            )
        ):
            raise RuntimeError(
                "Selected terminal no longer matches "
                "the authoritative terminal identity."
            )

        reported_data_path = getattr(
            terminal_info,
            "data_path",
            None,
        )

        if not isinstance(
            reported_data_path,
            str,
        ):
            raise RuntimeError(
                "Reported terminal data path is invalid."
            )

        if (
            _windows_path_key(
                reported_data_path
            )
            != _windows_path_key(
                preflight_result.data_path
            )
        ):
            raise RuntimeError(
                "Selected terminal data path no longer matches "
                "the authoritative terminal identity."
            )

    @staticmethod
    def _verify_account_identity(
        *,
        preflight_result: CustomerMT5SetupPreflightResult,
        account_info: Any,
    ) -> None:
        server = getattr(
            account_info,
            "server",
            None,
        )

        account_number = getattr(
            account_info,
            "login",
            None,
        )

        margin_mode = getattr(
            account_info,
            "margin_mode",
            None,
        )

        if (
            not isinstance(
                server,
                str,
            )
            or not server
            or not isinstance(
                account_number,
                int,
            )
            or isinstance(
                account_number,
                bool,
            )
            or account_number <= 0
        ):
            raise RuntimeError(
                "Current customer account identity is invalid."
            )

        fingerprint = (
            f"{server}:{account_number}"
        )

        if (
            fingerprint
            != preflight_result.account_fingerprint
        ):
            raise RuntimeError(
                "Current customer account does not match "
                "the authoritative account identity."
            )

        if (
            margin_mode
            != preflight_result.margin_mode
        ):
            raise RuntimeError(
                "Current customer account mode does not match "
                "the authoritative account identity."
            )


def _windows_path_key(
    value: str,
) -> str:
    return os.path.normpath(
        str(
            Path(
                value
            )
        )
    ).replace(
        "/",
        "\\",
    ).casefold()
