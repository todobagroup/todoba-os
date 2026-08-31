"""
Build and execute the TODOBA Windows Customer Setup packaging proof.

This owner reproduces the validated PyInstaller packaging recipe.

It:
- requires the validated PyInstaller version
- builds an onedir Windows executable
- explicitly collects MetaTrader5 and NumPy
- builds entirely outside the repository
- executes the frozen smoke executable
- fails closed unless every required runtime marker is present

It does not:
- acquire or contain a real setup credential
- contact TODOBA Cloud
- provision a customer
- install TODOBA into MT5
- build the final commercial installer
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


_REQUIRED_PYINSTALLER_VERSION = "6.22.2"
_PROOF_DIRECTORY_NAME = "TODOBA_PyInstaller_Proof"
_EXECUTABLE_NAME = "TODOBA_Packaging_Smoke"

_REQUIRED_EXACT_MARKERS = (
    "TODOBA_PACKAGING_SMOKE=GREEN",
    "FROZEN=1",
    "TK=8.6",
    "METATRADER5=5.0.5735",
    "CUSTOMER_SETUP_LAUNCHER=READY",
)

_REQUIRED_PREFIX_MARKERS = (
    "TCL=8.6",
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _proof_root() -> Path:
    return (
        Path(tempfile.gettempdir())
        / _PROOF_DIRECTORY_NAME
    )


def _smoke_source_path() -> Path:
    return (
        _repository_root()
        / "scripts"
        / "customer_setup_packaging_smoke.py"
    )


def _packaged_executable_path() -> Path:
    return (
        _proof_root()
        / "dist"
        / _EXECUTABLE_NAME
        / f"{_EXECUTABLE_NAME}.exe"
    )


def _read_pyinstaller_version() -> str:
    try:
        return version(
            "pyinstaller"
        )
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "Required PyInstaller is not installed."
        ) from exc


def _validate_build_environment() -> None:
    pyinstaller_version = (
        _read_pyinstaller_version()
    )

    if (
        pyinstaller_version
        != _REQUIRED_PYINSTALLER_VERSION
    ):
        raise RuntimeError(
            "Unsupported PyInstaller version: "
            f"{pyinstaller_version!r}. "
            "Expected "
            f"{_REQUIRED_PYINSTALLER_VERSION!r}."
        )

    smoke_source = (
        _smoke_source_path()
    )

    if not smoke_source.is_file():
        raise RuntimeError(
            "Packaging smoke source is missing."
        )


def _prepare_proof_root() -> Path:
    proof_root = _proof_root()

    temp_root = (
        Path(
            tempfile.gettempdir()
        )
        .resolve()
    )

    resolved_proof_root = (
        proof_root.resolve()
    )

    if (
        resolved_proof_root.parent
        != temp_root
    ):
        raise RuntimeError(
            "Packaging proof root must be "
            "a direct child of the system "
            "temporary directory."
        )

    if proof_root.exists():
        shutil.rmtree(
            proof_root
        )

    proof_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    return proof_root


def _build_command() -> tuple[str, ...]:
    repository_root = (
        _repository_root()
    )

    proof_root = (
        _proof_root()
    )

    return (
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--console",
        "--name",
        _EXECUTABLE_NAME,
        "--paths",
        str(
            repository_root
        ),
        "--collect-all",
        "MetaTrader5",
        "--collect-all",
        "numpy",
        "--hidden-import",
        "numpy._core.multiarray",
        "--distpath",
        str(
            proof_root
            / "dist"
        ),
        "--workpath",
        str(
            proof_root
            / "build"
        ),
        "--specpath",
        str(
            proof_root
            / "spec"
        ),
        str(
            _smoke_source_path()
        ),
    )


def _run_build() -> None:
    completed = subprocess.run(
        _build_command(),
        cwd=_repository_root(),
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "PyInstaller packaging build failed."
        )

    packaged_executable = (
        _packaged_executable_path()
    )

    if not packaged_executable.is_file():
        raise RuntimeError(
            "Packaged smoke executable "
            "was not produced."
        )


def _run_packaged_smoke() -> tuple[str, ...]:
    packaged_executable = (
        _packaged_executable_path()
    )

    completed = subprocess.run(
        (
            str(
                packaged_executable
            ),
        ),
        cwd=packaged_executable.parent,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stdout = (
        completed.stdout
        or ""
    )

    stderr = (
        completed.stderr
        or ""
    )

    if stdout:
        print(
            stdout,
            end=(
                ""
                if stdout.endswith(
                    "\n"
                )
                else "\n"
            ),
        )

    if stderr:
        print(
            stderr,
            file=sys.stderr,
            end=(
                ""
                if stderr.endswith(
                    "\n"
                )
                else "\n"
            ),
        )

    if completed.returncode != 0:
        raise RuntimeError(
            "Packaged smoke executable failed."
        )

    output_lines = tuple(
        line.strip()
        for line in stdout.splitlines()
        if line.strip()
    )

    return output_lines


def _validate_smoke_output(
    output_lines: tuple[str, ...],
) -> None:
    output_set = set(
        output_lines
    )

    for marker in (
        _REQUIRED_EXACT_MARKERS
    ):
        if marker not in output_set:
            raise RuntimeError(
                "Packaged smoke output is "
                f"missing required marker: "
                f"{marker!r}."
            )

    for prefix in (
        _REQUIRED_PREFIX_MARKERS
    ):
        if not any(
            line.startswith(
                prefix
            )
            for line in output_lines
        ):
            raise RuntimeError(
                "Packaged smoke output is "
                "missing required marker "
                f"prefix: {prefix!r}."
            )


def run_packaging_proof() -> Path:
    _validate_build_environment()

    _prepare_proof_root()

    print(
        "TODOBA_PACKAGING_BUILD=START",
        flush=True,
    )

    _run_build()

    print(
        "TODOBA_PACKAGING_BUILD=GREEN",
        flush=True,
    )

    output_lines = (
        _run_packaged_smoke()
    )

    _validate_smoke_output(
        output_lines
    )

    executable_path = (
        _packaged_executable_path()
    )

    print(
        "TODOBA_WINDOWS_PACKAGING_PROOF=GREEN",
        flush=True,
    )

    print(
        "EXE="
        f"{executable_path}",
        flush=True,
    )

    return executable_path


def main() -> int:
    run_packaging_proof()

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )