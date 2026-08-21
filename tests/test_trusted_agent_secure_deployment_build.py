"""
TODOBA Trusted Agent Secure Deployment Build Tests

CAP 3H Owner 3 proof:

A provisioned Trusted Agent must be compiled inside an
isolated build environment that combines:

- MetaTrader standard MQL5 libraries
- TODOBA material from the provisioned deployment only

Build success is authoritative only when:

- the MetaEditor compile log reports zero errors
- a non-empty EX5 exists

The MetaEditor process exit code is not authoritative.

These tests use proof-only credentials and a fake compiler.
"""

import importlib
from pathlib import Path

import pytest

from scripts.provision_trusted_agent_deployment import (
    provision_trusted_agent_deployment,
)


ROOT_DIR = Path(__file__).resolve().parents[1]

MQL5_SOURCE_ROOT = (
    ROOT_DIR
    / "MQL5"
)


AGENT_ID = "trusted-agent-build-owner-proof"

ACCOUNT_FINGERPRINT = (
    "proof-broker:990001"
)

AGENT_SECRET = (
    "proof-build-agent-secret"
)

EXECUTION_SECRET = (
    "proof-build-execution-secret"
)

CONTROL_SECRET = (
    "proof-build-control-secret"
)


def load_builder():
    module = importlib.import_module(
        "scripts.build_trusted_agent_deployment"
    )

    return (
        module
        .build_trusted_agent_deployment
    )


def provision_agent(
    tmp_path: Path,
) -> Path:
    return provision_trusted_agent_deployment(
        mql5_source_root=MQL5_SOURCE_ROOT,
        output_root=(
            tmp_path
            / "deployments"
        ),
        agent_id=AGENT_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
        agent_secret=AGENT_SECRET,
        execution_mission_signing_secret=(
            EXECUTION_SECRET
        ),
        control_mission_signing_secret=(
            CONTROL_SECRET
        ),
    )


def create_platform_mql5_root(
    tmp_path: Path,
) -> Path:
    root = (
        tmp_path
        / "platform"
        / "MQL5"
    )

    include_root = (
        root
        / "Include"
    )

    trade_directory = (
        include_root
        / "Trade"
    )

    trade_directory.mkdir(
        parents=True
    )

    (
        trade_directory
        / "Trade.mqh"
    ).write_text(
        "// proof MetaTrader standard Trade library\n",
        encoding="utf-8",
    )

    platform_execution = (
        include_root
        / "TODOBAExecution"
    )

    platform_control = (
        include_root
        / "TODOBAControl"
    )

    platform_security = (
        include_root
        / "TODOBASecurity"
    )

    platform_execution.mkdir(
        parents=True
    )

    platform_control.mkdir(
        parents=True
    )

    platform_security.mkdir(
        parents=True
    )

    (
        platform_execution
        / "TODOBAAgentCredentials.mqh"
    ).write_text(
        "PLATFORM_CREDENTIAL_MUST_NOT_SURVIVE\n",
        encoding="utf-8",
    )

    (
        platform_execution
        / "platform_only_execution.mqh"
    ).write_text(
        "PLATFORM_EXECUTION_MUST_NOT_SURVIVE\n",
        encoding="utf-8",
    )

    (
        platform_control
        / "platform_only_control.mqh"
    ).write_text(
        "PLATFORM_CONTROL_MUST_NOT_SURVIVE\n",
        encoding="utf-8",
    )

    (
        platform_security
        / "platform_only_security.mqh"
    ).write_text(
        "PLATFORM_SECURITY_MUST_NOT_SURVIVE\n",
        encoding="utf-8",
    )

    return root


def provisioned_credential_path(
    deployment_root: Path,
) -> Path:
    return (
        deployment_root
        / "MQL5"
        / "Include"
        / "TODOBAExecution"
        / "TODOBAAgentCredentials.mqh"
    )


def provisioned_agent_path(
    deployment_root: Path,
) -> Path:
    return (
        deployment_root
        / "MQL5"
        / "Experts"
        / "TODOBA_Trusted_Agent.mq5"
    )


def expected_artifact_path(
    deployment_root: Path,
) -> Path:
    return (
        deployment_root
        / "artifact"
        / "TODOBA_Trusted_Agent.ex5"
    )


def test_build_uses_standard_platform_library_and_only_provisioned_todoba_material(
    tmp_path: Path,
) -> None:
    deployment_root = provision_agent(
        tmp_path
    )

    platform_root = (
        create_platform_mql5_root(
            tmp_path
        )
    )

    provisioned_credentials = (
        provisioned_credential_path(
            deployment_root
        ).read_bytes()
    )

    provisioned_agent = (
        provisioned_agent_path(
            deployment_root
        ).read_bytes()
    )

    compiled_ex5 = (
        b"TODOBA-PROOF-EX5"
    )

    compiler_calls = 0

    def compiler_runner(
        *,
        agent_path: Path,
        mql5_root: Path,
        log_path: Path,
    ) -> int:
        nonlocal compiler_calls

        compiler_calls += 1

        build_include = (
            mql5_root
            / "Include"
        )

        assert (
            build_include
            / "Trade"
            / "Trade.mqh"
        ).is_file()

        build_credentials = (
            build_include
            / "TODOBAExecution"
            / "TODOBAAgentCredentials.mqh"
        )

        assert build_credentials.is_file()

        assert (
            build_credentials.read_bytes()
            == provisioned_credentials
        )

        assert (
            not (
                build_include
                / "TODOBAExecution"
                / "platform_only_execution.mqh"
            ).exists()
        )

        assert (
            not (
                build_include
                / "TODOBAControl"
                / "platform_only_control.mqh"
            ).exists()
        )

        assert (
            not (
                build_include
                / "TODOBASecurity"
                / "platform_only_security.mqh"
            ).exists()
        )

        assert (
            agent_path.read_bytes()
            == provisioned_agent
        )

        agent_path.with_suffix(
            ".ex5"
        ).write_bytes(
            compiled_ex5
        )

        log_path.write_text(
            (
                "MetaEditor proof compile\n"
                "Result: 0 errors, 2 warnings, "
                "100 ms elapsed\n"
            ),
            encoding="utf-8",
        )

        # Deliberately non-zero.
        # MetaEditor exit code is not build authority.
        return 1

    builder = load_builder()

    artifact = builder(
        deployment_root=deployment_root,
        platform_mql5_root=platform_root,
        build_root=(
            tmp_path
            / "isolated-build"
        ),
        compiler_runner=compiler_runner,
    )

    assert compiler_calls == 1

    assert artifact == (
        expected_artifact_path(
            deployment_root
        )
    )

    assert artifact.is_file()

    assert artifact.read_bytes() == (
        compiled_ex5
    )

    assert artifact.stat().st_size > 0

    assert not (
        deployment_root
        / "MQL5"
    ).exists()

    assert not (
        tmp_path
        / "isolated-build"
    ).exists()

    artifact_directory = (
        artifact.parent
    )

    assert not list(
        artifact_directory.glob(
            "*.mq5"
        )
    )

    assert not list(
        artifact_directory.glob(
            "*.mqh"
        )
    )


def test_compile_log_rejects_errors_even_when_compiler_exit_code_is_zero(
    tmp_path: Path,
) -> None:
    deployment_root = provision_agent(
        tmp_path
    )

    platform_root = (
        create_platform_mql5_root(
            tmp_path
        )
    )

    def compiler_runner(
        *,
        agent_path: Path,
        mql5_root: Path,
        log_path: Path,
    ) -> int:
        assert mql5_root.is_dir()

        agent_path.with_suffix(
            ".ex5"
        ).write_bytes(
            b"INVALID-EX5-MUST-NOT-BE-PACKAGED"
        )

        log_path.write_text(
            (
                "MetaEditor proof compile\n"
                "Result: 13 errors, 1 warnings, "
                "100 ms elapsed\n"
            ),
            encoding="utf-8",
        )

        # Deliberately zero.
        # A zero process exit code must not override
        # errors reported by the compile log.
        return 0

    builder = load_builder()

    with pytest.raises(
        RuntimeError,
        match=(
            "MetaEditor compilation contains errors"
        ),
    ):
        builder(
            deployment_root=deployment_root,
            platform_mql5_root=platform_root,
            build_root=(
                tmp_path
                / "isolated-build"
            ),
            compiler_runner=compiler_runner,
        )

    assert not (
        expected_artifact_path(
            deployment_root
        )
    ).exists()

    assert not (
        deployment_root
        / "MQL5"
    ).exists()

    assert not (
        tmp_path
        / "isolated-build"
    ).exists()


def test_zero_error_compile_log_without_ex5_is_rejected(
    tmp_path: Path,
) -> None:
    deployment_root = provision_agent(
        tmp_path
    )

    platform_root = (
        create_platform_mql5_root(
            tmp_path
        )
    )

    def compiler_runner(
        *,
        agent_path: Path,
        mql5_root: Path,
        log_path: Path,
    ) -> int:
        assert agent_path.is_file()
        assert mql5_root.is_dir()

        log_path.write_text(
            (
                "MetaEditor proof compile\n"
                "Result: 0 errors, 0 warnings, "
                "100 ms elapsed\n"
            ),
            encoding="utf-8",
        )

        return 1

    builder = load_builder()

    with pytest.raises(
        RuntimeError,
        match="EX5",
    ):
        builder(
            deployment_root=deployment_root,
            platform_mql5_root=platform_root,
            build_root=(
                tmp_path
                / "isolated-build"
            ),
            compiler_runner=compiler_runner,
        )

    assert not (
        expected_artifact_path(
            deployment_root
        )
    ).exists()

    assert not (
        deployment_root
        / "MQL5"
    ).exists()

    assert not (
        tmp_path
        / "isolated-build"
    ).exists()


def test_utf16_metaeditor_compile_log_is_accepted(
    tmp_path: Path,
) -> None:
    deployment_root = provision_agent(
        tmp_path
    )

    platform_root = (
        create_platform_mql5_root(
            tmp_path
        )
    )

    compiled_ex5 = (
        b"TODOBA-UTF16-PROOF-EX5"
    )

    def compiler_runner(
        *,
        agent_path: Path,
        mql5_root: Path,
        log_path: Path,
    ) -> int:
        assert agent_path.is_file()
        assert mql5_root.is_dir()

        agent_path.with_suffix(
            ".ex5"
        ).write_bytes(
            compiled_ex5
        )

        log_path.write_text(
            (
                "\r\n"
                "MetaEditor real-format proof compile\r\n"
                "Result: 0 errors, 2 warnings, "
                "100 ms elapsed, cpu='X64 Regular'\r\n"
            ),
            encoding="utf-16",
        )

        # Real MetaEditor may return non-zero even
        # when the compile log reports zero errors.
        return 1

    builder = load_builder()

    artifact = builder(
        deployment_root=deployment_root,
        platform_mql5_root=platform_root,
        build_root=(
            tmp_path
            / "isolated-build"
        ),
        compiler_runner=compiler_runner,
    )

    assert artifact == (
        expected_artifact_path(
            deployment_root
        )
    )

    assert artifact.is_file()

    assert artifact.read_bytes() == (
        compiled_ex5
    )

    assert not (
        deployment_root
        / "MQL5"
    ).exists()

    assert not (
        tmp_path
        / "isolated-build"
    ).exists()


def test_build_root_inside_repository_is_rejected_before_copying_material(
    tmp_path: Path,
    monkeypatch,
) -> None:
    deployment_root = provision_agent(
        tmp_path
    )

    platform_root = (
        create_platform_mql5_root(
            tmp_path
        )
    )

    forbidden_build_root = (
        ROOT_DIR
        / "CAP3H_FORBIDDEN_BUILD_PROOF"
    )

    assert not forbidden_build_root.exists()

    builder_module = importlib.import_module(
        "scripts.build_trusted_agent_deployment"
    )

    copytree_called = False

    def forbidden_copytree(
        *args,
        **kwargs,
    ):
        nonlocal copytree_called

        copytree_called = True

        raise AssertionError(
            "copytree must not run when build_root "
            "is inside the repository."
        )

    monkeypatch.setattr(
        builder_module.shutil,
        "copytree",
        forbidden_copytree,
    )

    builder = (
        builder_module
        .build_trusted_agent_deployment
    )

    with pytest.raises(
        ValueError,
        match="build_root",
    ):
        builder(
            deployment_root=deployment_root,
            platform_mql5_root=platform_root,
            build_root=forbidden_build_root,
            compiler_runner=lambda **kwargs: 0,
        )

    assert copytree_called is False

    assert not forbidden_build_root.exists()


def test_platform_todoba_material_never_enters_isolated_build_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    deployment_root = provision_agent(
        tmp_path
    )

    platform_root = (
        create_platform_mql5_root(
            tmp_path
        )
    )

    builder_module = importlib.import_module(
        "scripts.build_trusted_agent_deployment"
    )

    original_copytree = (
        builder_module.shutil.copytree
    )

    platform_include_root = (
        platform_root
        / "Include"
    ).resolve()

    platform_copy_observed = False

    def guarded_copytree(
        *args,
        **kwargs,
    ):
        nonlocal platform_copy_observed

        source_path = Path(
            args[0]
        ).resolve()

        destination_path = Path(
            args[1]
        ).resolve()

        result = original_copytree(
            *args,
            **kwargs,
        )

        if source_path == platform_include_root:
            platform_copy_observed = True

            assert not (
                destination_path
                / "TODOBAExecution"
            ).exists()

            assert not (
                destination_path
                / "TODOBAControl"
            ).exists()

            assert not (
                destination_path
                / "TODOBASecurity"
            ).exists()

        return result

    monkeypatch.setattr(
        builder_module.shutil,
        "copytree",
        guarded_copytree,
    )

    compiled_ex5 = (
        b"TODOBA-PLATFORM-ISOLATION-PROOF"
    )

    def compiler_runner(
        *,
        agent_path: Path,
        mql5_root: Path,
        log_path: Path,
    ) -> int:
        agent_path.with_suffix(
            ".ex5"
        ).write_bytes(
            compiled_ex5
        )

        log_path.write_text(
            (
                "MetaEditor proof compile\n"
                "Result: 0 errors, 0 warnings, "
                "100 ms elapsed\n"
            ),
            encoding="utf-8",
        )

        return 0

    artifact = (
        builder_module
        .build_trusted_agent_deployment(
            deployment_root=deployment_root,
            platform_mql5_root=platform_root,
            build_root=(
                tmp_path
                / "isolated-build"
            ),
            compiler_runner=compiler_runner,
        )
    )

    assert platform_copy_observed is True

    assert artifact.is_file()

    assert artifact.read_bytes() == (
        compiled_ex5
    )


def test_missing_provisioned_agent_cleans_plaintext_before_build_starts(
    tmp_path: Path,
) -> None:
    deployment_root = provision_agent(
        tmp_path
    )

    platform_root = (
        create_platform_mql5_root(
            tmp_path
        )
    )

    deployment_mql5_root = (
        deployment_root
        / "MQL5"
    )

    credential_path = (
        provisioned_credential_path(
            deployment_root
        )
    )

    agent_path = (
        provisioned_agent_path(
            deployment_root
        )
    )

    assert credential_path.is_file()
    assert agent_path.is_file()

    agent_path.unlink()

    assert not agent_path.exists()
    assert credential_path.is_file()

    build_root = (
        tmp_path
        / "isolated-build"
    )

    artifact_path = (
        expected_artifact_path(
            deployment_root
        )
    )

    builder = load_builder()

    with pytest.raises(
        FileNotFoundError,
        match="Provisioned Trusted Agent",
    ):
        builder(
            deployment_root=deployment_root,
            platform_mql5_root=platform_root,
            build_root=build_root,
            compiler_runner=lambda **kwargs: 0,
        )

    assert not deployment_mql5_root.exists()

    assert not build_root.exists()

    assert not artifact_path.exists()

def test_deployment_mql5_cannot_be_platform_mql5_root(
    tmp_path: Path,
) -> None:
    deployment_root = provision_agent(
        tmp_path
    )

    deployment_mql5_root = (
        deployment_root
        / "MQL5"
    )

    assert deployment_mql5_root.is_dir()

    trade_directory = (
        deployment_mql5_root
        / "Include"
        / "Trade"
    )

    trade_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        trade_directory
        / "Trade.mqh"
    ).write_text(
        "// destructive-path isolation proof\n",
        encoding="utf-8",
    )

    platform_sentinel = (
        deployment_mql5_root
        / "PLATFORM_MQL5_MUST_SURVIVE.txt"
    )

    platform_sentinel.write_text(
        "PLATFORM-MQL5-SENTINEL\n",
        encoding="utf-8",
    )

    build_root = (
        tmp_path
        / "isolated-build"
    )

    compiler_called = False

    def compiler_runner(
        *,
        agent_path: Path,
        mql5_root: Path,
        log_path: Path,
    ) -> int:
        nonlocal compiler_called

        compiler_called = True

        agent_path.with_suffix(
            ".ex5"
        ).write_bytes(
            b"TODOBA-DESTRUCTIVE-PATH-PROOF"
        )

        log_path.write_text(
            (
                "MetaEditor proof compile\n"
                "Result: 0 errors, 0 warnings, "
                "100 ms elapsed\n"
            ),
            encoding="utf-8",
        )

        return 0

    builder = load_builder()

    with pytest.raises(
        ValueError,
        match="platform_mql5_root",
    ):
        builder(
            deployment_root=deployment_root,
            platform_mql5_root=(
                deployment_mql5_root
            ),
            build_root=build_root,
            compiler_runner=compiler_runner,
        )

    assert compiler_called is False

    assert deployment_mql5_root.is_dir()

    assert platform_sentinel.is_file()

    assert (
        platform_sentinel.read_text(
            encoding="utf-8"
        )
        == "PLATFORM-MQL5-SENTINEL\n"
    )

    assert not build_root.exists()
