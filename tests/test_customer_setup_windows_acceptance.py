"""
Tests for frozen TODOBA Setup acceptance process boundary.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import scripts.customer_setup_windows_acceptance as acceptance


def test_acceptance_url_requires_plain_loopback_origin(
) -> None:
    assert (
        acceptance
        .normalize_acceptance_base_url(
            " http://127.0.0.1:8123/ "
        )
        == "http://127.0.0.1:8123"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "https://127.0.0.1:8123",
        "http://localhost:8123",
        "http://0.0.0.0:8123",
        "http://192.168.1.10:8123",
        "http://example.com:8123",
        "http://127.0.0.1",
        "http://127.0.0.1:8123/api",
        "http://127.0.0.1:8123/?x=1",
        "http://127.0.0.1:8123/#fragment",
        "http://user@127.0.0.1:8123",
        "http://user:secret@127.0.0.1:8123",
        "http://127.0.0.1:0",
        "http://127.0.0.1:65536",
    ],
)
def test_acceptance_url_rejects_noncanonical_or_nonloopback_values(
    value,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        (
            acceptance
            .normalize_acceptance_base_url(
                value
            )
        )


def test_acceptance_url_requires_string(
) -> None:
    with pytest.raises(
        TypeError,
        match="must be str",
    ):
        acceptance.normalize_acceptance_base_url(
            123
        )


def test_child_environment_does_not_mutate_parent(
) -> None:
    parent = {
        "EXISTING": "value",
        "TODOBA_CLOUD_BASE_URL": (
            "https://api.todobagroup.com"
        ),
    }

    result = (
        acceptance
        .build_acceptance_environment(
            setup_base_url=(
                "http://127.0.0.1:8123"
            ),
            parent_environment=parent,
        )
    )

    assert result is not parent

    assert parent == {
        "EXISTING": "value",
        "TODOBA_CLOUD_BASE_URL": (
            "https://api.todobagroup.com"
        ),
    }

    assert result[
        "EXISTING"
    ] == "value"

    assert result[
        "TODOBA_CLOUD_BASE_URL"
    ] == "http://127.0.0.1:8123"


def test_parent_environment_requires_dict(
) -> None:
    with pytest.raises(
        TypeError,
        match="parent_environment must be dict",
    ):
        acceptance.build_acceptance_environment(
            setup_base_url=(
                "http://127.0.0.1:8123"
            ),
            parent_environment=object(),
        )


def test_require_production_executable_accepts_locked_name(
    tmp_path,
) -> None:
    executable = (
        tmp_path
        / "TODOBA Trading AI Setup.exe"
    )

    executable.write_bytes(
        b"MZ"
    )

    assert (
        acceptance
        .require_production_executable(
            executable
        )
        == executable.resolve()
    )


def test_require_production_executable_rejects_wrong_name(
    tmp_path,
) -> None:
    executable = (
        tmp_path
        / "wrong.exe"
    )

    executable.write_bytes(
        b"MZ"
    )

    with pytest.raises(
        RuntimeError,
        match="name is invalid",
    ):
        acceptance.require_production_executable(
            executable
        )


def test_require_production_executable_rejects_missing_file(
    tmp_path,
) -> None:
    executable = (
        tmp_path
        / "TODOBA Trading AI Setup.exe"
    )

    with pytest.raises(
        RuntimeError,
        match="is not available",
    ):
        acceptance.require_production_executable(
            executable
        )


def test_launch_passes_only_executable_on_command_line(
    monkeypatch,
    tmp_path,
) -> None:
    executable = (
        tmp_path
        / "TODOBA Trading AI Setup.exe"
    )

    executable.write_bytes(
        b"MZ"
    )

    observed = {}

    class FakeProcess:
        pass

    fake_process = FakeProcess()

    def fake_popen(
        command,
        *,
        cwd,
        env,
        shell,
    ):
        observed[
            "command"
        ] = command

        observed[
            "cwd"
        ] = cwd

        observed[
            "env"
        ] = env

        observed[
            "shell"
        ] = shell

        return fake_process

    monkeypatch.setattr(
        acceptance.subprocess,
        "Popen",
        fake_popen,
    )

    parent = {
        "SAFE_PARENT_VALUE": "present",
    }

    result = (
        acceptance
        .launch_frozen_customer_setup(
            setup_base_url=(
                "http://127.0.0.1:8123"
            ),
            executable_path=executable,
            parent_environment=parent,
        )
    )

    assert result is fake_process

    assert observed[
        "command"
    ] == [
        str(
            executable.resolve()
        ),
    ]

    assert observed[
        "cwd"
    ] == executable.resolve().parent

    assert observed[
        "shell"
    ] is False

    assert observed[
        "env"
    ][
        "TODOBA_CLOUD_BASE_URL"
    ] == "http://127.0.0.1:8123"

    assert observed[
        "env"
    ][
        "SAFE_PARENT_VALUE"
    ] == "present"

    assert parent == {
        "SAFE_PARENT_VALUE": "present",
    }


def test_acceptance_owner_has_no_customer_credential_input_surface(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_acceptance.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    function_names = {
        node.name
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    }

    assert function_names == {
        "normalize_acceptance_base_url",
        "build_acceptance_environment",
        "require_production_executable",
        "launch_frozen_customer_setup",
    }

    forbidden_parameter_names = {
        "authorization_code",
        "code_verifier",
        "setup_launch_credential",
        "handoff_credential",
        "continuation_credential",
        "customer_id",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
    }

    for node in tree.body:
        if not isinstance(
            node,
            ast.FunctionDef,
        ):
            continue

        parameters = {
            argument.arg
            for argument in (
                list(
                    node.args.args
                )
                + list(
                    node.args.kwonlyargs
                )
            )
        }

        assert (
            forbidden_parameter_names
            .isdisjoint(
                parameters
            )
        )


def test_acceptance_owner_has_no_server_or_business_authority(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_acceptance.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_modules = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imported_modules.add(
                    alias.name
                )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
        ):
            imported_modules.add(
                node.module
            )

    forbidden_roots = {
        "fastapi",
        "uvicorn",
        "httpx",
        "requests",
    }

    imported_roots = {
        module.split(
            ".",
            1,
        )[0]
        for module in imported_modules
    }

    assert (
        forbidden_roots
        .isdisjoint(
            imported_roots
        )
    )

    forbidden_commercial_tokens = (
        "CustomerIdentityRegistry",
        "CustomerDeploymentRegistry",
        "CustomerSetupBootstrapAuthorizationService",
        "CustomerSetupActivationService",
        "CustomerSetupHandoffService",
        "CustomerDeploymentPackageBuildWorker",
        "CustomerDeploymentPackagePublication",
    )

    for token in forbidden_commercial_tokens:
        assert token not in source


def test_acceptance_owner_does_not_embed_production_cloud_url(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_acceptance.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "https://api.todobagroup.com"
        not in source
    )


def test_acceptance_owner_has_no_shell_execution(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_acceptance.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    calls = [
        node
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            ast.Call,
        )
    ]

    popen_calls = [
        node
        for node in calls
        if (
            isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr
            == "Popen"
        )
    ]

    assert len(
        popen_calls
    ) == 1

    keyword_values = {
        keyword.arg: keyword.value
        for keyword in popen_calls[
            0
        ].keywords
    }

    shell_value = keyword_values[
        "shell"
    ]

    assert isinstance(
        shell_value,
        ast.Constant,
    )

    assert (
        shell_value.value
        is False
    )
