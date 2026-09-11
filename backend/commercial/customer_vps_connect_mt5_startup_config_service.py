"""
TODOBA Customer VPS Connect MT5 Startup Config Service.

Writes one dedicated TODOBA startup config artifact for the exact
customer MT5 runtime preparation flow.

This owner has filesystem authority only for its dedicated config.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tempfile


_CONFIG_FILENAME = "TODOBA_VPS_Startup.ini"

_FORBIDDEN_TOKENS = (
    "Login=",
    "Password=",
    "AllowLiveTrading",
    "WebRequest",
    "AgentSecret",
    "MissionSigningSecret",
    "[Experts]",
    "[Common]",
)


@dataclass(
    frozen=True,
)
class CustomerVPSConnectMT5StartupConfigResult:
    config_path: str
    already_present: bool

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.config_path,
            str,
        ):
            raise TypeError(
                "config_path must be str."
            )

        normalized = self.config_path.strip()

        if not normalized:
            raise ValueError(
                "config_path is required."
            )

        object.__setattr__(
            self,
            "config_path",
            normalized,
        )

        if not isinstance(
            self.already_present,
            bool,
        ):
            raise TypeError(
                "already_present must be bool."
            )


class CustomerVPSConnectMT5StartupConfigService:
    """
    Write one dedicated fail-closed TODOBA startup config.
    """

    def write(
        self,
        *,
        directory: Path,
        config_text: str,
    ) -> CustomerVPSConnectMT5StartupConfigResult:
        if not isinstance(
            directory,
            Path,
        ):
            raise TypeError(
                "directory must be Path."
            )

        if not isinstance(
            config_text,
            str,
        ):
            raise TypeError(
                "config_text must be str."
            )

        normalized_text = config_text.strip()

        if not normalized_text:
            raise ValueError(
                "config_text must not be empty."
            )

        for token in _FORBIDDEN_TOKENS:
            if token.casefold() in config_text.casefold():
                raise ValueError(
                    "startup config contains forbidden authority."
                )

        if directory.exists():
            if directory.is_symlink():
                raise RuntimeError(
                    "Startup config directory must not be "
                    "a symbolic link."
                )

            if not directory.is_dir():
                raise RuntimeError(
                    "Startup config directory is not a directory."
                )
        else:
            directory.mkdir(
                parents=True,
                exist_ok=False,
            )

        resolved_directory = directory.resolve(
            strict=True
        )

        if not resolved_directory.is_dir():
            raise ValueError(
                "directory must be an existing directory."
            )

        target = (
            resolved_directory
            / _CONFIG_FILENAME
        )

        resolved_target_parent = target.parent.resolve(
            strict=True
        )

        if (
            resolved_target_parent
            != resolved_directory
        ):
            raise RuntimeError(
                "startup config target escapes directory."
            )

        if target.is_symlink():
            raise RuntimeError(
                "startup config target must not be a symbolic link."
            )

        encoded = config_text.encode(
            "utf-8"
        )

        if target.exists():
            if not target.is_file():
                raise RuntimeError(
                    "Existing startup config target is not a file."
                )

            existing = target.read_bytes()

            if existing == encoded:
                return CustomerVPSConnectMT5StartupConfigResult(
                    config_path=str(
                        target.resolve()
                    ),
                    already_present=True,
                )

            raise FileExistsError(
                "Existing TODOBA startup config conflicts "
                "with requested config."
            )

        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".TODOBA_VPS_Startup.",
                suffix=".tmp",
                dir=resolved_directory,
                delete=False,
            ) as temporary_file:
                temporary_file.write(
                    encoded
                )
                temporary_file.flush()
                os.fsync(
                    temporary_file.fileno()
                )

                temporary_path = Path(
                    temporary_file.name
                )

            if temporary_path.read_bytes() != encoded:
                raise RuntimeError(
                    "Temporary startup config verification failed."
                )

            os.rename(
                temporary_path,
                target,
            )

            temporary_path = None

            if target.read_bytes() != encoded:
                raise RuntimeError(
                    "Installed startup config verification failed."
                )

            return CustomerVPSConnectMT5StartupConfigResult(
                config_path=str(
                    target.resolve()
                ),
                already_present=False,
            )

        finally:
            if (
                temporary_path is not None
                and temporary_path.exists()
            ):
                temporary_path.unlink()
