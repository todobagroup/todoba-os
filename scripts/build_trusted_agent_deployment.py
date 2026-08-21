"""
TODOBA Trusted Agent Secure Deployment Builder

Builds one provisioned Trusted Agent inside an isolated
MQL5 compilation workspace.

Security rules:

- never compile against platform TODOBA material
- use platform MQL5 only for standard MetaTrader libraries
- overlay TODOBA material from the provisioned deployment
- preserve provisioned source and credentials unchanged
- never trust MetaEditor process exit code as build authority
- require compile log Result: 0 errors
- require a non-empty EX5 before packaging
- package only the compiled EX5 artifact
"""

from collections.abc import Callable
from pathlib import Path
import hashlib
import re
import shutil


_TODOBA_INCLUDE_DIRECTORIES = (
    "TODOBAExecution",
    "TODOBAControl",
    "TODOBASecurity",
)

_AGENT_RELATIVE_PATH = (
    Path("Experts")
    / "TODOBA_Trusted_Agent.mq5"
)

_CREDENTIAL_RELATIVE_PATH = (
    Path("Include")
    / "TODOBAExecution"
    / "TODOBAAgentCredentials.mqh"
)

_ARTIFACT_RELATIVE_PATH = (
    Path("artifact")
    / "TODOBA_Trusted_Agent.ex5"
)

_RESULT_PATTERN = re.compile(
    r"(?im)^Result:\s*(\d+)\s+errors?\b"
)


CompilerRunner = Callable[
    ...,
    int,
]


def _require_directory(
    *,
    name: str,
    path: Path,
) -> Path:
    resolved = Path(
        path
    ).resolve()

    if not resolved.is_dir():
        raise FileNotFoundError(
            f"{name} does not exist."
        )

    return resolved


def _require_file(
    *,
    name: str,
    path: Path,
) -> Path:
    resolved = Path(
        path
    ).resolve()

    if not resolved.is_file():
        raise FileNotFoundError(
            f"{name} does not exist."
        )

    return resolved


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as source:
        for chunk in iter(
            lambda: source.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def _copy_platform_standard_include(
    *,
    platform_mql5_root: Path,
    build_include_root: Path,
) -> None:
    platform_include_root = (
        platform_mql5_root
        / "Include"
    )

    if not platform_include_root.is_dir():
        raise FileNotFoundError(
            "Platform MQL5 Include directory "
            "does not exist."
        )

    shutil.copytree(
        platform_include_root,
        build_include_root,
        ignore=shutil.ignore_patterns(
            *_TODOBA_INCLUDE_DIRECTORIES
        ),
    )

    standard_trade = (
        build_include_root
        / "Trade"
        / "Trade.mqh"
    )

    if not standard_trade.is_file():
        raise FileNotFoundError(
            "MetaTrader standard Trade.mqh "
            "is missing."
        )


def _remove_platform_todoba_material(
    *,
    build_include_root: Path,
) -> None:
    for directory_name in (
        _TODOBA_INCLUDE_DIRECTORIES
    ):
        candidate = (
            build_include_root
            / directory_name
        )

        if candidate.exists():
            shutil.rmtree(
                candidate
            )

    for directory_name in (
        _TODOBA_INCLUDE_DIRECTORIES
    ):
        candidate = (
            build_include_root
            / directory_name
        )

        if candidate.exists():
            raise RuntimeError(
                "Platform TODOBA material "
                "could not be removed."
            )


def _overlay_provisioned_todoba_material(
    *,
    provisioned_include_root: Path,
    build_include_root: Path,
) -> None:
    copied = 0

    for directory_name in (
        _TODOBA_INCLUDE_DIRECTORIES
    ):
        source = (
            provisioned_include_root
            / directory_name
        )

        if not source.exists():
            continue

        if not source.is_dir():
            raise RuntimeError(
                "Provisioned TODOBA include "
                "material is not a directory."
            )

        destination = (
            build_include_root
            / directory_name
        )

        shutil.copytree(
            source,
            destination,
        )

        copied += 1

    if copied == 0:
        raise RuntimeError(
            "Provisioned TODOBA include "
            "material is missing."
        )


def _verify_exact_copy(
    *,
    source: Path,
    destination: Path,
    name: str,
) -> None:
    if not destination.is_file():
        raise RuntimeError(
            f"{name} was not copied."
        )

    if (
        _sha256(
            source
        )
        != _sha256(
            destination
        )
    ):
        raise RuntimeError(
            f"{name} copy verification failed."
        )


def _read_compile_error_count(
    *,
    log_path: Path,
) -> int:
    if not log_path.is_file():
        raise RuntimeError(
            "MetaEditor compile log is missing."
        )

    raw_log = log_path.read_bytes()

    try:
        if raw_log.startswith(
            (
                b"\xff\xfe",
                b"\xfe\xff",
            )
        ):
            compile_log = raw_log.decode(
                "utf-16"
            )

        elif raw_log.startswith(
            b"\xef\xbb\xbf"
        ):
            compile_log = raw_log.decode(
                "utf-8-sig"
            )

        else:
            compile_log = raw_log.decode(
                "utf-8"
            )

    except UnicodeDecodeError as error:
        raise RuntimeError(
            "MetaEditor compile log encoding "
            "is unsupported."
        ) from error

    matches = list(
        _RESULT_PATTERN.finditer(
            compile_log
        )
    )

    if not matches:
        raise RuntimeError(
            "MetaEditor compilation result "
            "is missing."
        )

    return int(
        matches[-1].group(
            1
        )
    )


def build_trusted_agent_deployment(
    *,
    deployment_root: Path,
    platform_mql5_root: Path,
    build_root: Path,
    compiler_runner: CompilerRunner,
) -> Path:
    deployment_root = (
        _require_directory(
            name="Trusted Agent deployment",
            path=deployment_root,
        )
    )

    build_root = Path(
        build_root
    ).resolve()

    deployment_mql5_root = (
        deployment_root
        / "MQL5"
    ).resolve()

    platform_mql5_root = Path(
        platform_mql5_root
    ).resolve()

    if (
        deployment_mql5_root
        == platform_mql5_root
        or deployment_mql5_root
        in platform_mql5_root.parents
        or platform_mql5_root
        in deployment_mql5_root.parents
    ):
        raise ValueError(
            "platform_mql5_root must not overlap "
            "the deployment MQL5 root."
        )

    artifact_path = (
        deployment_root
        / _ARTIFACT_RELATIVE_PATH
    )

    artifact_directory = (
        artifact_path.parent
    )

    build_root_owned = False
    artifact_directory_owned = False

    try:
        platform_mql5_root = (
            _require_directory(
                name="Platform MQL5 root",
                path=platform_mql5_root,
            )
        )

        repository_root = (
            Path(__file__).resolve().parents[1]
        )

        if (
            build_root == repository_root
            or repository_root in build_root.parents
        ):
            raise ValueError(
                "build_root must be outside "
                "the repository."
            )

        if build_root.exists():
            raise FileExistsError(
                "Trusted Agent build workspace "
                "already exists."
            )

        build_root_owned = True

        provisioned_include_root = (
            deployment_mql5_root
            / "Include"
        )

        provisioned_agent = (
            _require_file(
                name="Provisioned Trusted Agent",
                path=(
                    deployment_mql5_root
                    / _AGENT_RELATIVE_PATH
                ),
            )
        )

        provisioned_credential = (
            _require_file(
                name=(
                    "Provisioned Trusted Agent "
                    "credential"
                ),
                path=(
                    deployment_mql5_root
                    / _CREDENTIAL_RELATIVE_PATH
                ),
            )
        )

        if artifact_directory.exists():
            raise FileExistsError(
                "Trusted Agent artifact "
                "already exists."
            )

        artifact_directory_owned = True

        build_mql5_root = (
            build_root
            / "MQL5"
        )

        build_include_root = (
            build_mql5_root
            / "Include"
        )

        build_experts_root = (
            build_mql5_root
            / "Experts"
        )
        _copy_platform_standard_include(
            platform_mql5_root=(
                platform_mql5_root
            ),
            build_include_root=(
                build_include_root
            ),
        )

        _remove_platform_todoba_material(
            build_include_root=(
                build_include_root
            ),
        )

        _overlay_provisioned_todoba_material(
            provisioned_include_root=(
                provisioned_include_root
            ),
            build_include_root=(
                build_include_root
            ),
        )

        build_credential = (
            build_mql5_root
            / _CREDENTIAL_RELATIVE_PATH
        )

        _verify_exact_copy(
            source=provisioned_credential,
            destination=build_credential,
            name=(
                "Provisioned Trusted Agent "
                "credential"
            ),
        )

        build_experts_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        build_agent = (
            build_mql5_root
            / _AGENT_RELATIVE_PATH
        )

        shutil.copy2(
            provisioned_agent,
            build_agent,
        )

        _verify_exact_copy(
            source=provisioned_agent,
            destination=build_agent,
            name="Provisioned Trusted Agent",
        )

        build_log = (
            build_agent.with_suffix(
                ".log"
            )
        )

        compiler_runner(
            agent_path=build_agent,
            mql5_root=build_mql5_root,
            log_path=build_log,
        )

        error_count = (
            _read_compile_error_count(
                log_path=build_log
            )
        )

        if error_count != 0:
            raise RuntimeError(
                "MetaEditor compilation "
                "contains errors."
            )

        build_ex5 = (
            build_agent.with_suffix(
                ".ex5"
            )
        )

        if not build_ex5.is_file():
            raise RuntimeError(
                "MetaEditor compilation "
                "reported zero errors but "
                "EX5 is missing."
            )

        if build_ex5.stat().st_size <= 0:
            raise RuntimeError(
                "MetaEditor generated an "
                "empty EX5 artifact."
            )

        artifact_directory.mkdir(
            parents=True
        )

        shutil.copy2(
            build_ex5,
            artifact_path,
        )

        if not artifact_path.is_file():
            raise RuntimeError(
                "Trusted Agent EX5 artifact "
                "was not packaged."
            )

        if artifact_path.stat().st_size <= 0:
            raise RuntimeError(
                "Packaged Trusted Agent EX5 "
                "artifact is empty."
            )

        _verify_exact_copy(
            source=build_ex5,
            destination=artifact_path,
            name="Trusted Agent EX5 artifact",
        )

        if deployment_mql5_root.exists():
            shutil.rmtree(
                deployment_mql5_root
            )

        if (
            build_root_owned
            and build_root.exists()
        ):
            shutil.rmtree(
                build_root
            )

    except Exception:
        if (
            artifact_directory_owned
            and artifact_directory.exists()
        ):
            shutil.rmtree(
                artifact_directory
            )

        if deployment_mql5_root.exists():
            shutil.rmtree(
                deployment_mql5_root
            )

        if (
            build_root_owned
            and build_root.exists()
        ):
            shutil.rmtree(
                build_root
            )

        raise

    return artifact_path
