import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


_REPOSITORY_ROOT = (
    Path(__file__).resolve().parents[1]
)

_STARTUP_PATH = (
    _REPOSITORY_ROOT
    / "scripts"
    / "start_todoba.ps1"
)

_CONTROLLER_PATH = (
    _REPOSITORY_ROOT
    / "scripts"
    / "control_todoba.ps1"
)

_PACKAGE_BUILDER_ENTRYPOINT = (
    _REPOSITORY_ROOT
    / "backend"
    / "start_package_builder.py"
)

_MAIN_PATH = (
    _REPOSITORY_ROOT
    / "backend"
    / "main.py"
)


def _read(
    path: Path,
) -> str:
    return path.read_text(
        encoding="utf-8-sig"
    )


def test_production_startup_supervises_package_builder_as_third_component():
    source = _read(
        _STARTUP_PATH
    )

    assert (
        'Module = "backend.start_api"'
        in source
    )

    assert (
        'Module = "backend.start_executor"'
        in source
    )

    assert (
        'Module = "backend.start_package_builder"'
        in source
    ), (
        "TODOBA production startup must supervise "
        "the automatic customer package builder."
    )


def test_startup_validation_exposes_package_builder_module():
    source = _read(
        _STARTUP_PATH
    )

    assert (
        'PACKAGE_BUILDER_MODULE=backend.start_package_builder'
        in source
    ), (
        "Startup validation must make package-builder "
        "ownership visible to operators."
    )


def test_runtime_controller_owns_and_counts_package_builder():
    source = _read(
        _CONTROLLER_PATH
    )

    assert (
        "PackageBuilderProcessCount"
        in source
    ), (
        "Runtime status must report the supervised "
        "package-builder process count."
    )

    assert (
        "backend\\.start_package_builder"
        in source
        or "backend.start_package_builder"
        in source
    ), (
        "Runtime process recognition must include "
        "backend.start_package_builder."
    )


def test_runtime_ready_requires_live_package_builder():
    source = _read(
        _CONTROLLER_PATH
    )

    compact = (
        source
        .replace(
            "`r",
            ""
        )
        .replace(
            "`n",
            ""
        )
    )

    assert (
        "$status.PackageBuilderProcessCount -gt 0"
        in compact
    ), (
        "TODOBA Runtime must not report READY unless "
        "the automatic package builder is alive."
    )


def test_package_builder_entrypoint_is_separate_runtime_owner():
    assert (
        _PACKAGE_BUILDER_ENTRYPOINT.is_file()
    ), (
        "Production automatic package building requires "
        "a dedicated backend.start_package_builder owner."
    )

    source = _read(
        _PACKAGE_BUILDER_ENTRYPOINT
    )

    assert (
        "process_customer_deployment_package_build_requests"
        in source
    )

    tree = ast.parse(
        source
    )

    imported_modules = set()

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.update(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module is not None:
                imported_modules.add(
                    node.module
                )

    assert (
        "backend.main"
        not in imported_modules
    ), (
        "Package-builder process must not import "
        "backend.main."
    )

    assert (
        "sleep"
        in source.lower()
    ), (
        "Supervised package-builder owner must remain "
        "alive and poll the durable queue."
    )


def test_backend_main_still_owns_no_package_build_execution():
    source = _read(
        _MAIN_PATH
    )

    forbidden = (
        "process_customer_deployment_package_build_requests",
        "CustomerDeploymentPackageBuildWorker(",
        "build_trusted_agent_deployment(",
    )

    for token in forbidden:
        assert token not in source, (
            "backend.main must remain free of package "
            f"build execution ownership: {token}"
        )


def test_package_builder_runtime_fails_closed_without_machine_paths(
    monkeypatch,
):
    from backend import (
        start_package_builder,
    )

    for environment_name in (
        "TODOBA_PACKAGE_BUILDER_PLATFORM_MQL5_ROOT",
        "TODOBA_PACKAGE_BUILDER_METAEDITOR_PATH",
        "TODOBA_PACKAGE_BUILDER_WORKSPACE_ROOT",
    ):
        monkeypatch.delenv(
            environment_name,
            raising=False,
        )

    with pytest.raises(
        RuntimeError,
        match=(
            "TODOBA_PACKAGE_BUILDER_PLATFORM_MQL5_ROOT "
            "is required"
        ),
    ):
        start_package_builder.run_package_builder()


def test_package_builder_runtime_polls_queue_and_remains_supervised(
    monkeypatch,
    tmp_path,
):
    from backend import (
        start_package_builder,
    )

    platform_root = (
        tmp_path
        / "platform"
        / "MQL5"
    )

    platform_root.mkdir(
        parents=True,
    )

    metaeditor_path = (
        tmp_path
        / "MetaEditor64.exe"
    )

    metaeditor_path.write_bytes(
        b"test-metaeditor"
    )

    workspace_root = (
        tmp_path
        / "workspace"
    )

    workspace_root.mkdir()

    monkeypatch.setenv(
        "TODOBA_PACKAGE_BUILDER_PLATFORM_MQL5_ROOT",
        str(
            platform_root
        ),
    )

    monkeypatch.setenv(
        "TODOBA_PACKAGE_BUILDER_METAEDITOR_PATH",
        str(
            metaeditor_path
        ),
    )

    monkeypatch.setenv(
        "TODOBA_PACKAGE_BUILDER_WORKSPACE_ROOT",
        str(
            workspace_root
        ),
    )

    monkeypatch.delenv(
        "TODOBA_PACKAGE_BUILDER_POLL_SECONDS",
        raising=False,
    )

    observed = {
        "process_count": 0,
        "sleep_seconds": None,
    }

    def fake_process_queue_once(
        **kwargs,
    ):
        observed[
            "process_count"
        ] += 1

        assert (
            kwargs["platform_mql5_root"]
            == platform_root.resolve()
        )

        assert (
            kwargs["metaeditor_path"]
            == metaeditor_path.resolve()
        )

        assert (
            kwargs["workspace_root"]
            == workspace_root.resolve()
        )

        return SimpleNamespace(
            total=0,
            built=0,
            already_ready=0,
            busy=0,
        )

    class StopAfterFirstPoll(
        Exception,
    ):
        pass

    def fake_sleep(
        seconds,
    ):
        observed[
            "sleep_seconds"
        ] = seconds

        raise StopAfterFirstPoll()

    monkeypatch.setattr(
        start_package_builder,
        "_process_queue_once",
        fake_process_queue_once,
    )

    monkeypatch.setattr(
        start_package_builder.time,
        "sleep",
        fake_sleep,
    )

    with pytest.raises(
        StopAfterFirstPoll,
    ):
        start_package_builder.run_package_builder()

    assert (
        observed["process_count"]
        == 1
    )

    assert (
        observed["sleep_seconds"]
        == 2.0
    )


def test_package_builder_runtime_does_not_swallow_queue_failure(
    monkeypatch,
    tmp_path,
):
    from backend import (
        start_package_builder,
    )

    platform_root = (
        tmp_path
        / "platform"
        / "MQL5"
    )

    platform_root.mkdir(
        parents=True,
    )

    metaeditor_path = (
        tmp_path
        / "MetaEditor64.exe"
    )

    metaeditor_path.write_bytes(
        b"test-metaeditor"
    )

    workspace_root = (
        tmp_path
        / "workspace"
    )

    workspace_root.mkdir()

    monkeypatch.setenv(
        "TODOBA_PACKAGE_BUILDER_PLATFORM_MQL5_ROOT",
        str(
            platform_root
        ),
    )

    monkeypatch.setenv(
        "TODOBA_PACKAGE_BUILDER_METAEDITOR_PATH",
        str(
            metaeditor_path
        ),
    )

    monkeypatch.setenv(
        "TODOBA_PACKAGE_BUILDER_WORKSPACE_ROOT",
        str(
            workspace_root
        ),
    )

    def fail_queue(
        **kwargs,
    ):
        raise RuntimeError(
            "synthetic queue failure"
        )

    monkeypatch.setattr(
        start_package_builder,
        "_process_queue_once",
        fail_queue,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic queue failure",
    ):
        start_package_builder.run_package_builder()
