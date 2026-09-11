"""
Windows packaging owner for standalone TODOBA VPS Connect.

This owner:
- packages the production VPS Connect entrypoint
- uses the validated PyInstaller toolchain
- emits an onedir Windows GUI application
- applies the TODOBA Trading icon
- keeps build artifacts outside the repository
- owns packaging only
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


_VALIDATED_PYINSTALLER_VERSION = "6.22.2"

_PRODUCT_NAME = "TODOBA VPS Setup"

_ENTRYPOINT_RELATIVE_PATH = (
    Path("scripts")
    / "customer_vps_connect.py"
)

_ICON_RELATIVE_PATH = (
    Path("assets")
    / "TODOBA_Trading.ico"
)

_ARTIFACT_DIRECTORY_NAME = (
    "TODOBA Build Artifacts"
)

_BUILD_DIRECTORY_NAME = (
    "customer_vps_connect_windows"
)


def _repository_root(
) -> Path:
    return Path(
        __file__
    ).resolve().parents[1]


def _entrypoint_path(
) -> Path:
    return (
        _repository_root()
        / _ENTRYPOINT_RELATIVE_PATH
    ).resolve()


def _icon_path(
) -> Path:
    return (
        _repository_root()
        / _ICON_RELATIVE_PATH
    ).resolve()


def _artifact_root(
) -> Path:
    return (
        _repository_root().parent
        / _ARTIFACT_DIRECTORY_NAME
        / _BUILD_DIRECTORY_NAME
    ).resolve()


def _build_root(
) -> Path:
    return (
        _artifact_root()
        / "build"
    ).resolve()


def _dist_root(
) -> Path:
    return (
        _artifact_root()
        / "dist"
    ).resolve()


def _spec_root(
) -> Path:
    return (
        _artifact_root()
        / "spec"
    ).resolve()


def _executable_path(
) -> Path:
    return (
        _dist_root()
        / _PRODUCT_NAME
        / f"{_PRODUCT_NAME}.exe"
    ).resolve()


def _read_pyinstaller_version(
) -> str:
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


def _validate_build_environment(
) -> None:
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

    entrypoint = _entrypoint_path()

    if not entrypoint.is_file():
        raise RuntimeError(
            "VPS Connect production entrypoint is missing."
        )

    icon = _icon_path()

    if not icon.is_file():
        raise RuntimeError(
            "TODOBA Trading icon is missing."
        )


def _build_command(
) -> tuple[str, ...]:
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
        "--workpath",
        str(
            _build_root()
        ),
        "--distpath",
        str(
            _dist_root()
        ),
        "--specpath",
        str(
            _spec_root()
        ),
        str(
            _entrypoint_path()
        ),
    )


def build_customer_vps_connect_windows_executable(
) -> Path:
    _validate_build_environment()

    _build_root().mkdir(
        parents=True,
        exist_ok=True,
    )

    _dist_root().mkdir(
        parents=True,
        exist_ok=True,
    )

    _spec_root().mkdir(
        parents=True,
        exist_ok=True,
    )

    subprocess.run(
        _build_command(),
        check=True,
        cwd=_repository_root(),
    )

    executable = (
        _executable_path()
    )

    if not executable.is_file():
        raise RuntimeError(
            "TODOBA VPS Connect executable was not produced."
        )

    return executable


def main(
) -> int:
    executable = (
        build_customer_vps_connect_windows_executable()
    )

    print(
        executable
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )