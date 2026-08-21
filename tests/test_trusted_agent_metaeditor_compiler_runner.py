"""
TODOBA Trusted Agent MetaEditor Compiler Runner Tests

CAP 3H Owner 4 proof:

The production MetaEditor runner must:

- invoke the exact provisioned Agent source
- compile against the exact isolated MQL5 root
- request a MetaEditor compile log
- return the MetaEditor process exit code unchanged
- never treat the process exit code as build success authority
- reject a missing MetaEditor executable
- reject a missing compile log
- remove any stale compile log before invocation

The secure build owner remains responsible for parsing the
compile log and deciding whether the build is GREEN.
"""

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_runner_class():
    module = importlib.import_module(
        "scripts.trusted_agent_metaeditor_compiler_runner"
    )

    return (
        module
        .MetaEditorCompilerRunner
    )


def create_build_surface(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
    Path,
]:
    metaeditor_path = (
        tmp_path
        / "MetaEditor64.exe"
    )

    metaeditor_path.write_bytes(
        b"PROOF-METAEDITOR"
    )

    mql5_root = (
        tmp_path
        / "isolated"
        / "MQL5"
    )

    agent_path = (
        mql5_root
        / "Experts"
        / "TODOBA_Trusted_Agent.mq5"
    )

    agent_path.parent.mkdir(
        parents=True
    )

    (
        mql5_root
        / "Include"
    ).mkdir(
        parents=True
    )

    agent_path.write_text(
        "// proof provisioned Trusted Agent\n",
        encoding="utf-8",
    )

    log_path = (
        agent_path.with_suffix(
            ".log"
        )
    )

    return (
        metaeditor_path,
        mql5_root,
        agent_path,
        log_path,
    )


def test_runner_invokes_exact_metaeditor_build_and_returns_exit_code_without_interpreting_it(
    tmp_path: Path,
) -> None:
    (
        metaeditor_path,
        mql5_root,
        agent_path,
        log_path,
    ) = create_build_surface(
        tmp_path
    )

    calls: list[
        tuple[
            list[str],
            bool,
        ]
    ] = []

    def process_runner(
        arguments: list[str],
        *,
        check: bool,
    ):
        calls.append(
            (
                arguments,
                check,
            )
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
        # The runner must not interpret this
        # as build failure.
        return SimpleNamespace(
            returncode=1
        )

    runner_class = load_runner_class()

    runner = runner_class(
        metaeditor_path=metaeditor_path,
        process_runner=process_runner,
    )

    exit_code = runner(
        agent_path=agent_path,
        mql5_root=mql5_root,
        log_path=log_path,
    )

    assert exit_code == 1

    assert calls == [
        (
            [
                str(
                    metaeditor_path.resolve()
                ),
                (
                    "/compile:"
                    + str(
                        agent_path.resolve()
                    )
                ),
                (
                    "/inc:"
                    + str(
                        mql5_root.resolve()
                    )
                ),
                "/log",
            ],
            False,
        )
    ]

    assert log_path.is_file()

    assert (
        "Result: 0 errors"
        in log_path.read_text(
            encoding="utf-8"
        )
    )


def test_runner_rejects_missing_metaeditor_before_process_execution(
    tmp_path: Path,
) -> None:
    (
        metaeditor_path,
        mql5_root,
        agent_path,
        log_path,
    ) = create_build_surface(
        tmp_path
    )

    metaeditor_path.unlink()

    called = False

    def process_runner(
        arguments: list[str],
        *,
        check: bool,
    ):
        nonlocal called

        called = True

        return SimpleNamespace(
            returncode=0
        )

    runner_class = load_runner_class()

    runner = runner_class(
        metaeditor_path=metaeditor_path,
        process_runner=process_runner,
    )

    with pytest.raises(
        FileNotFoundError,
        match="MetaEditor",
    ):
        runner(
            agent_path=agent_path,
            mql5_root=mql5_root,
            log_path=log_path,
        )

    assert called is False


def test_runner_rejects_missing_compile_log_regardless_of_exit_code(
    tmp_path: Path,
) -> None:
    (
        metaeditor_path,
        mql5_root,
        agent_path,
        log_path,
    ) = create_build_surface(
        tmp_path
    )

    def process_runner(
        arguments: list[str],
        *,
        check: bool,
    ):
        assert arguments
        assert check is False

        # Deliberately zero.
        # No compile log must still fail closed.
        return SimpleNamespace(
            returncode=0
        )

    runner_class = load_runner_class()

    runner = runner_class(
        metaeditor_path=metaeditor_path,
        process_runner=process_runner,
    )

    with pytest.raises(
        RuntimeError,
        match="compile log",
    ):
        runner(
            agent_path=agent_path,
            mql5_root=mql5_root,
            log_path=log_path,
        )


def test_runner_removes_stale_compile_log_before_invocation(
    tmp_path: Path,
) -> None:
    (
        metaeditor_path,
        mql5_root,
        agent_path,
        log_path,
    ) = create_build_surface(
        tmp_path
    )

    log_path.write_text(
        (
            "STALE LOG MUST NOT SURVIVE\n"
            "Result: 0 errors, 0 warnings\n"
        ),
        encoding="utf-8",
    )

    stale_log_was_present_during_process = (
        None
    )

    def process_runner(
        arguments: list[str],
        *,
        check: bool,
    ):
        nonlocal stale_log_was_present_during_process

        assert arguments
        assert check is False

        stale_log_was_present_during_process = (
            log_path.exists()
        )

        # Simulate MetaEditor failing to create
        # a fresh compile log.
        return SimpleNamespace(
            returncode=0
        )

    runner_class = load_runner_class()

    runner = runner_class(
        metaeditor_path=metaeditor_path,
        process_runner=process_runner,
    )

    with pytest.raises(
        RuntimeError,
        match="compile log",
    ):
        runner(
            agent_path=agent_path,
            mql5_root=mql5_root,
            log_path=log_path,
        )

    assert (
        stale_log_was_present_during_process
        is False
    )

    assert not log_path.exists()
