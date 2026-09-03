"""
Tests for the isolated TODOBA Setup production server harness.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

import scripts.customer_setup_windows_acceptance_server as server


@pytest.mark.parametrize(
    "port",
    [
        1,
        8123,
        65535,
    ],
)
def test_loopback_port_accepts_valid_ports(
    port,
) -> None:
    assert (
        server.validate_loopback_port(
            port
        )
        == port
    )


@pytest.mark.parametrize(
    "port",
    [
        0,
        -1,
        65536,
    ],
)
def test_loopback_port_rejects_out_of_range_values(
    port,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        server.validate_loopback_port(
            port
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "8123",
        8123.0,
        None,
    ],
)
def test_loopback_port_requires_integer(
    value,
) -> None:
    with pytest.raises(
        TypeError,
    ):
        server.validate_loopback_port(
            value
        )


def test_master_key_requires_nonempty_string(
) -> None:
    assert (
        server.validate_encoded_master_key(
            " encoded-test-key "
        )
        == "encoded-test-key"
    )

    with pytest.raises(
        ValueError,
    ):
        server.validate_encoded_master_key(
            "   "
        )

    with pytest.raises(
        TypeError,
    ):
        server.validate_encoded_master_key(
            123
        )


def test_server_environment_is_child_only_and_isolated(
    tmp_path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    package_root = (
        tmp_path
        / "packages"
    )

    parent = {
        "EXISTING": "value",
        "TODOBA_CONTROL_PLANE_DATA_ROOT": (
            "production-control-plane"
        ),
        "TODOBA_CUSTOMER_PACKAGE_ROOT": (
            "production-packages"
        ),
        "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY": (
            "production-master-key"
        ),
    }

    result = (
        server.build_server_environment(
            control_plane_root=(
                control_plane_root
            ),
            package_root=(
                package_root
            ),
            encoded_master_key=(
                "acceptance-master-key"
            ),
            parent_environment=parent,
        )
    )

    assert result is not parent

    assert parent[
        "TODOBA_CONTROL_PLANE_DATA_ROOT"
    ] == "production-control-plane"

    assert parent[
        "TODOBA_CUSTOMER_PACKAGE_ROOT"
    ] == "production-packages"

    assert parent[
        "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY"
    ] == "production-master-key"

    assert result[
        "TODOBA_CONTROL_PLANE_DATA_ROOT"
    ] == str(
        control_plane_root.resolve()
    )

    assert result[
        "TODOBA_CUSTOMER_PACKAGE_ROOT"
    ] == str(
        package_root.resolve()
    )

    assert result[
        "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY"
    ] == "acceptance-master-key"


def test_control_plane_and_package_roots_must_be_distinct(
    tmp_path,
) -> None:
    same = (
        tmp_path
        / "same"
    )

    with pytest.raises(
        ValueError,
        match="must be distinct",
    ):
        server.build_server_environment(
            control_plane_root=same,
            package_root=same,
            encoded_master_key="key",
            parent_environment={},
        )


def test_server_environment_requires_mapping(
    tmp_path,
) -> None:
    with pytest.raises(
        TypeError,
        match="parent_environment must be Mapping",
    ):
        server.build_server_environment(
            control_plane_root=(
                tmp_path
                / "control-plane"
            ),
            package_root=(
                tmp_path
                / "packages"
            ),
            encoded_master_key="key",
            parent_environment=object(),
        )


def test_prepare_control_plane_provisions_before_runtime(
    monkeypatch,
    tmp_path,
) -> None:
    observed = {}

    def fake_provision(
        *,
        control_plane_root,
        confirm_runtime_stopped,
    ):
        observed[
            "control_plane_root"
        ] = control_plane_root

        observed[
            "confirm_runtime_stopped"
        ] = confirm_runtime_stopped

    monkeypatch.setattr(
        server,
        "provision_customer_setup_control_plane",
        fake_provision,
    )

    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    package_root = (
        tmp_path
        / "packages"
    )

    server.prepare_isolated_control_plane(
        control_plane_root=(
            control_plane_root
        ),
        package_root=(
            package_root
        ),
    )

    assert (
        control_plane_root
        .is_dir()
    )

    assert (
        package_root
        .is_dir()
    )

    assert observed[
        "control_plane_root"
    ] == control_plane_root.resolve()

    assert observed[
        "confirm_runtime_stopped"
    ] is True


def test_server_start_uses_real_production_app_on_loopback(
    monkeypatch,
) -> None:
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
        server.subprocess,
        "Popen",
        fake_popen,
    )

    environment = {
        "SAFE": "value",
    }

    result = (
        server.start_production_server(
            port=8123,
            environment=environment,
        )
    )

    assert result is fake_process

    assert observed[
        "command"
    ] == [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8123",
        "--log-level",
        "warning",
    ]

    assert observed[
        "cwd"
    ] == server._repository_root()

    assert observed[
        "env"
    ] == environment

    assert observed[
        "env"
    ] is not environment

    assert observed[
        "shell"
    ] is False


def test_server_start_environment_requires_mapping(
) -> None:
    with pytest.raises(
        TypeError,
        match="environment must be Mapping",
    ):
        server.start_production_server(
            port=8123,
            environment=object(),
        )


def test_stop_returns_when_process_already_exited(
    monkeypatch,
) -> None:
    class FakePopen(
        subprocess.Popen
    ):
        def __init__(
            self,
        ):
            pass

        def poll(
            self,
        ):
            return 0

    process = FakePopen()

    observed = {
        "terminate": 0,
    }

    def terminate():
        observed[
            "terminate"
        ] += 1

    monkeypatch.setattr(
        process,
        "terminate",
        terminate,
    )

    server.stop_production_server(
        process=process
    )

    assert observed[
        "terminate"
    ] == 0


def test_stop_terminates_clean_process(
    monkeypatch,
) -> None:
    class FakePopen(
        subprocess.Popen
    ):
        def __init__(
            self,
        ):
            self.exited = False

        def poll(
            self,
        ):
            if self.exited:
                return 0

            return None

        def terminate(
            self,
        ):
            self.exited = True

        def wait(
            self,
            *,
            timeout,
        ):
            assert timeout == 3.0
            return 0

    process = FakePopen()

    server.stop_production_server(
        process=process,
        timeout_seconds=3.0,
    )

    assert (
        process.exited
        is True
    )


def test_stop_kills_process_after_timeout(
    monkeypatch,
) -> None:
    class FakePopen(
        subprocess.Popen
    ):
        def __init__(
            self,
        ):
            self.killed = False
            self.wait_calls = 0

        def poll(
            self,
        ):
            return None

        def terminate(
            self,
        ):
            return None

        def wait(
            self,
            *,
            timeout,
        ):
            assert timeout == 2.0

            self.wait_calls += 1

            if self.wait_calls == 1:
                raise subprocess.TimeoutExpired(
                    cmd="uvicorn",
                    timeout=timeout,
                )

            return 0

        def kill(
            self,
        ):
            self.killed = True

    process = FakePopen()

    server.stop_production_server(
        process=process,
        timeout_seconds=2.0,
    )

    assert (
        process.killed
        is True
    )

    assert (
        process.wait_calls
        == 2
    )


def test_server_owner_has_no_customer_or_authorization_surface(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_acceptance_server.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    forbidden_parameters = {
        "customer_id",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
        "authorization_code",
        "code_challenge_s256",
        "code_verifier",
        "setup_launch_credential",
        "handoff_credential",
        "continuation_credential",
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
            forbidden_parameters
            .isdisjoint(
                parameters
            )
        )


def test_server_owner_does_not_launch_customer_executable_or_build_package(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_acceptance_server.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "launch_frozen_customer_setup",
        "TODOBA Trading AI Setup.exe",
        "issue_customer_setup_bootstrap_authorization",
        "process_customer_deployment_package_build_requests",
        "CustomerDeploymentPackageBuildWorker",
    )

    for token in forbidden:
        assert token not in source


def test_server_owner_has_no_production_cloud_url(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_acceptance_server.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "https://api.todobagroup.com"
        not in source
    )


def test_server_owner_uses_shell_false(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_acceptance_server.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    popen_calls = [
        node
        for node in ast.walk(
            tree
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
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

    keywords = {
        keyword.arg: keyword.value
        for keyword
        in popen_calls[
            0
        ].keywords
    }

    shell = keywords[
        "shell"
    ]

    assert isinstance(
        shell,
        ast.Constant,
    )

    assert (
        shell.value
        is False
    )
