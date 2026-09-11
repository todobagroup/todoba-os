"""
TODOBA Customer VPS Connect MT5 Launcher Service.

Builds and delegates one exact customer MT5 startup invocation
using one dedicated TODOBA startup configuration artifact.

The caller supplies the process-launch boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any


_TERMINAL_FILENAME = "terminal64.exe"
_CONFIG_SUFFIX = ".ini"


@dataclass(
    frozen=True,
)
class CustomerVPSConnectMT5LaunchResult:
    process_id: int
    terminal_path: str
    config_path: str

    def __post_init__(
        self,
    ) -> None:
        if (
            not isinstance(
                self.process_id,
                int,
            )
            or isinstance(
                self.process_id,
                bool,
            )
            or self.process_id <= 0
        ):
            raise ValueError(
                "process_id must be a positive int."
            )

        for name in (
            "terminal_path",
            "config_path",
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


class CustomerVPSConnectMT5LauncherService:
    """
    Delegate one exact terminal startup invocation.
    """

    def __init__(
        self,
        *,
        process_launcher: Any,
    ) -> None:
        launch = getattr(
            process_launcher,
            "launch",
            None,
        )

        if not callable(
            launch
        ):
            raise TypeError(
                "process_launcher must provide callable launch()."
            )

        self._process_launcher = (
            process_launcher
        )

    def launch(
        self,
        *,
        terminal_path: str,
        config_path: str,
    ) -> CustomerVPSConnectMT5LaunchResult:
        normalized_terminal = (
            self._validate_terminal_path(
                terminal_path
            )
        )

        normalized_config = (
            self._validate_config_path(
                config_path
            )
        )

        process_id = (
            self._process_launcher.launch(
                executable=normalized_terminal,
                arguments=(
                    f"/config:{normalized_config}",
                ),
            )
        )

        if (
            not isinstance(
                process_id,
                int,
            )
            or isinstance(
                process_id,
                bool,
            )
            or process_id <= 0
        ):
            raise RuntimeError(
                "Process launcher returned invalid process id."
            )

        return CustomerVPSConnectMT5LaunchResult(
            process_id=process_id,
            terminal_path=normalized_terminal,
            config_path=normalized_config,
        )

    @staticmethod
    def _validate_terminal_path(
        value: str,
    ) -> str:
        normalized = (
            _normalize_safe_path_string(
                value,
                name="terminal_path",
            )
        )

        if (
            PureWindowsPath(
                normalized
            ).name.casefold()
            != _TERMINAL_FILENAME.casefold()
        ):
            raise ValueError(
                "terminal_path must identify terminal64.exe."
            )

        return normalized

    @staticmethod
    def _validate_config_path(
        value: str,
    ) -> str:
        normalized = (
            _normalize_safe_path_string(
                value,
                name="config_path",
            )
        )

        if (
            PureWindowsPath(
                normalized
            ).suffix.casefold()
            != _CONFIG_SUFFIX
        ):
            raise ValueError(
                "config_path must identify an INI file."
            )

        return normalized


def _normalize_safe_path_string(
    value: str,
    *,
    name: str,
) -> str:
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

    if any(
        character in normalized
        for character in (
            "\r",
            "\n",
            "\x00",
        )
    ):
        raise ValueError(
            f"{name} contains unsupported characters."
        )

    return normalized
