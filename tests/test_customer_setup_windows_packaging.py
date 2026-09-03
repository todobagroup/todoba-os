"""
Tests for TODOBA Trading AI Setup production Windows packaging.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys

import pytest

import scripts.build_customer_setup_windows as build_module


def test_product_identity_is_locked(
) -> None:
    assert (
        build_module._PRODUCT_NAME
        == "TODOBA Trading AI Setup"
    )

    assert (
        build_module._ENTRYPOINT_RELATIVE_PATH
        == (
            Path("scripts")
            / "customer_setup.py"
        )
    )

    assert (
        build_module._ICON_RELATIVE_PATH
        == (
            Path("assets")
            / "TODOBA_Trading.ico"
        )
    )


def test_build_environment_accepts_validated_pyinstaller(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        build_module,
        "_read_pyinstaller_version",
        lambda: "6.22.2",
    )

    build_module._validate_build_environment()


def test_build_environment_rejects_other_pyinstaller(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        build_module,
        "_read_pyinstaller_version",
        lambda: "6.22.1",
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported PyInstaller version",
    ):
        build_module._validate_build_environment()


def test_build_command_packages_authoritative_entrypoint(
) -> None:
    command = (
        build_module._build_command()
    )

    assert command[:3] == (
        sys.executable,
        "-m",
        "PyInstaller",
    )

    assert (
        command[-1]
        == str(
            build_module._entrypoint_path()
        )
    )

    assert (
        Path(
            command[-1]
        ).resolve()
        == (
            Path(__file__)
            .resolve()
            .parents[1]
            / "scripts"
            / "customer_setup.py"
        ).resolve()
    )


def test_build_command_is_windows_gui_onedir(
) -> None:
    command = (
        build_module._build_command()
    )

    assert "--onedir" in command
    assert "--windowed" in command

    assert "--onefile" not in command
    assert "--console" not in command


def test_build_command_uses_locked_product_name(
) -> None:
    command = (
        build_module._build_command()
    )

    name_index = (
        command.index(
            "--name"
        )
    )

    assert (
        command[
            name_index + 1
        ]
        == "TODOBA Trading AI Setup"
    )


def test_build_command_uses_todoba_icon(
) -> None:
    command = (
        build_module._build_command()
    )

    icon_index = (
        command.index(
            "--icon"
        )
    )

    configured_icon = Path(
        command[
            icon_index + 1
        ]
    ).resolve()

    assert (
        configured_icon
        == (
            Path(__file__)
            .resolve()
            .parents[1]
            / "assets"
            / "TODOBA_Trading.ico"
        ).resolve()
    )


def test_build_command_collects_mt5_and_numpy(
) -> None:
    command = (
        build_module._build_command()
    )

    collect_positions = [
        index
        for index, value
        in enumerate(command)
        if value == "--collect-all"
    ]

    collected = {
        command[
            index + 1
        ]
        for index
        in collect_positions
    }

    assert collected == {
        "MetaTrader5",
        "numpy",
    }

    hidden_index = (
        command.index(
            "--hidden-import"
        )
    )

    assert (
        command[
            hidden_index + 1
        ]
        == "numpy._core.multiarray"
    )


def test_build_artifacts_are_outside_repository(
) -> None:
    repository_root = (
        build_module
        ._repository_root()
        .resolve()
    )

    artifact_root = (
        build_module
        ._artifact_root()
        .resolve()
    )

    assert (
        repository_root
        not in artifact_root.parents
    )

    assert (
        artifact_root
        != repository_root
    )

    for option in (
        "--distpath",
        "--workpath",
        "--specpath",
    ):
        command = (
            build_module._build_command()
        )

        option_index = (
            command.index(
                option
            )
        )

        configured = Path(
            command[
                option_index + 1
            ]
        ).resolve()

        assert (
            configured
            == {
                "--distpath": (
                    build_module
                    ._dist_path()
                    .resolve()
                ),
                "--workpath": (
                    build_module
                    ._work_path()
                    .resolve()
                ),
                "--specpath": (
                    build_module
                    ._spec_path()
                    .resolve()
                ),
            }[
                option
            ]
        )

        assert (
            artifact_root
            in configured.parents
        )


def test_packaged_executable_has_customer_product_name(
) -> None:
    executable_path = (
        build_module
        ._packaged_executable_path()
    )

    assert (
        executable_path.name
        == "TODOBA Trading AI Setup.exe"
    )

    assert (
        executable_path.parent.name
        == "TODOBA Trading AI Setup"
    )


def test_build_execution_uses_repository_as_working_directory(
    monkeypatch,
) -> None:
    observed = {}

    def fake_run(
        command,
        *,
        cwd,
        check,
    ):
        observed[
            "command"
        ] = command

        observed[
            "cwd"
        ] = cwd

        observed[
            "check"
        ] = check

    monkeypatch.setattr(
        build_module.subprocess,
        "run",
        fake_run,
    )

    build_module._run_build()

    assert (
        observed[
            "command"
        ]
        == build_module._build_command()
    )

    assert (
        observed[
            "cwd"
        ]
        == build_module._repository_root()
    )

    assert (
        observed[
            "check"
        ]
        is True
    )


def test_build_flow_executes_gates_in_order(
    monkeypatch,
    tmp_path,
) -> None:
    events = []

    executable_path = (
        tmp_path
        / "TODOBA Trading AI Setup.exe"
    )

    def validate():
        events.append(
            "validate"
        )

    def prepare():
        events.append(
            "prepare"
        )

    def build():
        events.append(
            "build"
        )

        executable_path.write_bytes(
            b"production-executable-proof"
        )

    monkeypatch.setattr(
        build_module,
        "_validate_build_environment",
        validate,
    )

    monkeypatch.setattr(
        build_module,
        "_prepare_artifact_root",
        prepare,
    )

    monkeypatch.setattr(
        build_module,
        "_run_build",
        build,
    )

    monkeypatch.setattr(
        build_module,
        "_packaged_executable_path",
        lambda: executable_path,
    )

    result = (
        build_module
        .build_customer_setup_windows_executable()
    )

    assert result == executable_path

    assert events == [
        "validate",
        "prepare",
        "build",
    ]


def test_build_fails_if_executable_is_not_produced(
    monkeypatch,
    tmp_path,
) -> None:
    missing = (
        tmp_path
        / "TODOBA Trading AI Setup.exe"
    )

    monkeypatch.setattr(
        build_module,
        "_validate_build_environment",
        lambda: None,
    )

    monkeypatch.setattr(
        build_module,
        "_prepare_artifact_root",
        lambda: None,
    )

    monkeypatch.setattr(
        build_module,
        "_run_build",
        lambda: None,
    )

    monkeypatch.setattr(
        build_module,
        "_packaged_executable_path",
        lambda: missing,
    )

    with pytest.raises(
        RuntimeError,
        match="executable was not produced",
    ):
        (
            build_module
            .build_customer_setup_windows_executable()
        )


def test_build_owner_has_no_network_authority(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "build_customer_setup_windows.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_roots = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_roots.add(
                    alias.name.split(
                        ".",
                        1,
                    )[0]
                )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            imported_roots.add(
                node.module.split(
                    ".",
                    1,
                )[0]
            )

    assert {
        "httpx",
        "requests",
        "urllib3",
        "fastapi",
        "uvicorn",
    }.isdisjoint(
        imported_roots
    )


def test_build_owner_contains_no_customer_or_secret_authority(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "build_customer_setup_windows.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "customer_id",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
        "agent_secret",
        "execution_mission_signing_secret",
        "control_mission_signing_secret",
        "setup_handoff_credential",
        "continuation_credential",
        "authorization_code",
        "payment_id",
        "subscription_id",
        "https://api.todobagroup.com",
    )

    for token in forbidden:
        assert token not in source
