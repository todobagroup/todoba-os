"""
TODOBA VPS Connect Windows process launch boundary.

Owns only creation of one child process from an exact executable
and exact argument vector supplied by higher-level validated owners.

It has no MT5 account, credential, trading, migration, shutdown,
or VPS purchasing authority.
"""

from __future__ import annotations

from pathlib import Path
import subprocess


class CustomerVPSConnectWindowsProcessLauncher:
    """
    Launch one exact Windows executable without a command shell.
    """

    def launch(
        self,
        *,
        executable: str,
        arguments: tuple[str, ...],
    ) -> int:
        if not isinstance(
            executable,
            str,
        ):
            raise TypeError(
                "executable must be str."
            )

        normalized_executable = executable.strip()

        if not normalized_executable:
            raise ValueError(
                "executable is required."
            )

        if any(
            character in normalized_executable
            for character in (
                "\r",
                "\n",
                "\x00",
            )
        ):
            raise ValueError(
                "executable contains invalid characters."
            )

        executable_path = Path(
            normalized_executable
        )

        if not executable_path.exists():
            raise FileNotFoundError(
                "Executable does not exist."
            )

        if not executable_path.is_file():
            raise RuntimeError(
                "Executable is not a file."
            )

        if not isinstance(
            arguments,
            tuple,
        ):
            raise TypeError(
                "arguments must be tuple."
            )

        if not arguments:
            raise ValueError(
                "arguments must not be empty."
            )

        normalized_arguments = []

        for argument in arguments:
            if not isinstance(
                argument,
                str,
            ):
                raise TypeError(
                    "arguments must contain only str."
                )

            normalized_argument = argument.strip()

            if not normalized_argument:
                raise ValueError(
                    "argument is required."
                )

            if any(
                character in normalized_argument
                for character in (
                    "\r",
                    "\n",
                    "\x00",
                )
            ):
                raise ValueError(
                    "argument contains invalid characters."
                )

            normalized_arguments.append(
                normalized_argument
            )

        process = subprocess.Popen(
            [
                normalized_executable,
                *normalized_arguments,
            ]
        )

        process_id = getattr(
            process,
            "pid",
            None,
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

        return process_id
