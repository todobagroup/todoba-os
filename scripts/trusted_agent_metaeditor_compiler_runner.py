"""
TODOBA Trusted Agent MetaEditor Compiler Runner

Invokes MetaEditor for one isolated Trusted Agent build.

Responsibilities:

- invoke the exact MetaEditor executable
- compile the exact provisioned Agent source
- compile against the exact isolated MQL5 root
- request a fresh MetaEditor compile log
- return the MetaEditor process exit code unchanged

Important:

MetaEditor process exit code is not build authority.

The secure deployment builder is responsible for parsing
the compile log and requiring:

- Result: 0 errors
- a non-empty EX5 artifact
"""

from collections.abc import Callable
from pathlib import Path
import subprocess


ProcessRunner = Callable[
    ...,
    object,
]


class MetaEditorCompilerRunner:
    def __init__(
        self,
        *,
        metaeditor_path: Path,
        process_runner: ProcessRunner = subprocess.run,
    ) -> None:
        self._metaeditor_path = Path(
            metaeditor_path
        ).resolve()

        self._process_runner = (
            process_runner
        )

    def __call__(
        self,
        *,
        agent_path: Path,
        mql5_root: Path,
        log_path: Path,
    ) -> int:
        metaeditor_path = (
            self._metaeditor_path
        )

        agent_path = Path(
            agent_path
        ).resolve()

        mql5_root = Path(
            mql5_root
        ).resolve()

        log_path = Path(
            log_path
        ).resolve()

        if not metaeditor_path.is_file():
            raise FileNotFoundError(
                "MetaEditor executable "
                "does not exist."
            )

        if not agent_path.is_file():
            raise FileNotFoundError(
                "Trusted Agent source "
                "does not exist."
            )

        if not mql5_root.is_dir():
            raise FileNotFoundError(
                "Isolated MQL5 root "
                "does not exist."
            )

        if log_path.exists():
            if not log_path.is_file():
                raise RuntimeError(
                    "MetaEditor compile log path "
                    "is not a file."
                )

            log_path.unlink()

        arguments = [
            str(
                metaeditor_path
            ),
            (
                "/compile:"
                + str(
                    agent_path
                )
            ),
            (
                "/inc:"
                + str(
                    mql5_root
                )
            ),
            "/log",
        ]

        process = self._process_runner(
            arguments,
            check=False,
        )

        if not hasattr(
            process,
            "returncode",
        ):
            raise RuntimeError(
                "MetaEditor process result "
                "does not expose a return code."
            )

        exit_code = int(
            process.returncode
        )

        if not log_path.is_file():
            raise RuntimeError(
                "MetaEditor compile log "
                "was not created."
            )

        return exit_code
