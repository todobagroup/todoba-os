"""
TODOBA Trading AI Setup Windows Build Owner.

Builds the production customer-facing Windows Setup executable.

This owner:
- packages the authoritative production entrypoint
- uses the validated PyInstaller toolchain
- emits an onedir Windows GUI application
- applies the TODOBA Trading icon
- keeps build artifacts outside the repository
- owns packaging only, never customer or server authority
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


_VALIDATED_PYINSTALLER_VERSION = "6.22.2"

_PRODUCT_NAME = "TODOBA Trading AI Setup"

_ENTRYPOINT_RELATIVE_PATH = Path(
    "scripts"
) / "customer_setup.py"

_ICON_RELATIVE_PATH = Path(
    "assets"
) / "TODOBA_Trading.ico"

_ARTIFACT_DIRECTORY_NAME = (
    "TODOBA Build Artifacts"
)

_BUILD_DIRECTORY_NAME = (
    "customer_setup_windows"
)


def _repository_root() -> Path:
    return (
        Path(__file__)
        .resolve()
        .parents[1]
    )


def _artifact_root() -> Path:
    repository_root = (
        _repository_root()
    )

    return (
        repository_root.parent
        / _ARTIFACT_DIRECTORY_NAME
        / _BUILD_DIRECTORY_NAME
    )


def _entrypoint_path() -> Path:
    return (
        _repository_root()
        / _ENTRYPOINT_RELATIVE_PATH
    )


def _icon_path() -> Path:
    return (
        _repository_root()
        / _ICON_RELATIVE_PATH
    )


def _dist_path() -> Path:
    return (
        _artifact_root()
        / "dist"
    )


def _work_path() -> Path:
    return (
        _artifact_root()
        / "build"
    )


def _spec_path() -> Path:
    return (
        _artifact_root()
        / "spec"
    )


def _packaged_directory_path() -> Path:
    return (
        _dist_path()
        / _PRODUCT_NAME
    )


def _packaged_executable_path() -> Path:
    return (
        _packaged_directory_path()
        / f"{_PRODUCT_NAME}.exe"
    )


def _read_pyinstaller_version() -> str:
    import PyInstaller

    version = getattr(
        PyInstaller,
        "__version__",
        None,
    )

    if not isinstance(
        version,
        str,
    ):
        raise RuntimeError(
            "PyInstaller version is unavailable."
        )

    normalized = version.strip()

    if not normalized:
        raise RuntimeError(
            "PyInstaller version is unavailable."
        )

    return normalized


def _validate_build_environment() -> None:
    version = (
        _read_pyinstaller_version()
    )

    if (
        version
        != _VALIDATED_PYINSTALLER_VERSION
    ):
        raise RuntimeError(
            "Unsupported PyInstaller version. "
            f"Expected "
            f"{_VALIDATED_PYINSTALLER_VERSION}; "
            f"got {version}."
        )

    entrypoint_path = (
        _entrypoint_path()
    )

    if not entrypoint_path.is_file():
        raise RuntimeError(
            "Production customer Setup "
            "entrypoint is missing."
        )

    icon_path = (
        _icon_path()
    )

    if not icon_path.is_file():
        raise RuntimeError(
            "TODOBA Trading Setup icon "
            "is missing."
        )


def _prepare_artifact_root() -> None:
    artifact_root = (
        _artifact_root()
    )

    if artifact_root.exists():
        shutil.rmtree(
            artifact_root
        )

    _dist_path().mkdir(
        parents=True,
        exist_ok=False,
    )

    _work_path().mkdir(
        parents=True,
        exist_ok=False,
    )

    _spec_path().mkdir(
        parents=True,
        exist_ok=False,
    )


def _build_command() -> tuple[
    str,
    ...,
]:
    return (
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        _PRODUCT_NAME,
        "--icon",
        str(
            _icon_path()
        ),
        "--paths",
        str(
            _repository_root()
        ),
        "--collect-all",
        "MetaTrader5",
        "--collect-all",
        "numpy",
        "--hidden-import",
        "numpy._core.multiarray",
        "--distpath",
        str(
            _dist_path()
        ),
        "--workpath",
        str(
            _work_path()
        ),
        "--specpath",
        str(
            _spec_path()
        ),
        str(
            _entrypoint_path()
        ),
    )


def _run_build() -> None:
    subprocess.run(
        _build_command(),
        cwd=_repository_root(),
        check=True,
    )


def build_customer_setup_windows_executable(
) -> Path:
    """
    Build and return the production Setup executable path.
    """

    _validate_build_environment()
    _prepare_artifact_root()
    _run_build()

    executable_path = (
        _packaged_executable_path()
    )

    if not executable_path.is_file():
        raise RuntimeError(
            "Production customer Setup "
            "executable was not produced."
        )

    return executable_path


def main() -> int:
    executable_path = (
        build_customer_setup_windows_executable()
    )

    print(
        executable_path
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
