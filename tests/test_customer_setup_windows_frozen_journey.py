"""
Tests for the TODOBA real frozen Setup acceptance journey.
"""

from __future__ import annotations

import ast
import base64
from pathlib import Path
import subprocess
import sys

import pytest

import scripts.customer_setup_windows_frozen_journey as journey


def test_pkce_s256_challenge_accepts_canonical_value(
) -> None:
    challenge = (
        "A" * 43
    )

    assert (
        journey
        .validate_pkce_s256_challenge(
            f"  {challenge}  "
        )
        == challenge
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "A" * 42,
        "A" * 44,
        "A" * 42 + "=",
        "A" * 42 + "+",
        "A" * 42 + "/",
    ],
)
def test_pkce_s256_challenge_rejects_invalid_shape(
    value,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        journey.validate_pkce_s256_challenge(
            value
        )


def test_generated_master_key_decodes_to_exactly_32_bytes(
) -> None:
    encoded = (
        journey
        .generate_encoded_master_key()
    )

    decoded = base64.b64decode(
        encoded,
        altchars=b"-_",
        validate=True,
    )

    assert len(
        decoded
    ) == 32


def test_loopback_port_selection_returns_valid_port(
) -> None:
    port = (
        journey
        .select_loopback_port()
    )

    assert (
        1
        <= port
        <= 65535
    )


def test_acceptance_root_must_be_external_and_empty(
    tmp_path,
) -> None:
    root = (
        tmp_path
        / "acceptance"
    )

    (
        control_plane,
        packages,
        workspace,
    ) = (
        journey
        .prepare_acceptance_root(
            root
        )
    )

    assert (
        control_plane
        == root.resolve()
        / "control-plane"
    )

    assert (
        packages
        == root.resolve()
        / "packages"
    )

    assert workspace.is_dir()

    with pytest.raises(
        RuntimeError,
        match="must be empty",
    ):
        journey.prepare_acceptance_root(
            root
        )


def test_repository_local_acceptance_root_is_rejected(
) -> None:
    with pytest.raises(
        ValueError,
        match="outside the repository",
    ):
        journey.prepare_acceptance_root(
            journey._repository_root()
            / "acceptance"
        )


def test_identity_substrate_initializes_empty_registry_only(
    monkeypatch,
    tmp_path,
) -> None:
    observed = {
        "initialized": 0,
        "register": 0,
    }

    class FakeRegistry:
        def __init__(
            self,
            storage_path,
        ):
            observed[
                "storage_path"
            ] = storage_path

            self.ready = False

        def initialize_empty(
            self,
        ):
            observed[
                "initialized"
            ] += 1

            self.ready = True

        def is_ready(
            self,
        ):
            return self.ready

        def size(
            self,
        ):
            return 0

        def register(
            self,
            identity,
        ):
            observed[
                "register"
            ] += 1

            raise AssertionError(
                "G2B2 substrate must not register customers."
            )

    monkeypatch.setattr(
        journey,
        "CustomerIdentityRegistry",
        FakeRegistry,
    )

    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    identity_path = (
        journey
        .prepare_authoritative_identity_substrate(
            control_plane_root=(
                control_plane_root
            )
        )
    )

    assert identity_path == (
        control_plane_root.resolve()
        / "commercial"
        / "customer_identities.json"
    )

    assert observed[
        "storage_path"
    ] == identity_path

    assert observed[
        "initialized"
    ] == 1

    assert observed[
        "register"
    ] == 0


def test_identity_substrate_rejects_repository_local_root(
) -> None:
    with pytest.raises(
        ValueError,
        match="outside the repository",
    ):
        journey.prepare_authoritative_identity_substrate(
            control_plane_root=(
                journey._repository_root()
                / "control-plane"
            )
        )


def test_complete_runtime_substrate_creates_all_empty_prerequisites(
    tmp_path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    encoded_master_key = (
        journey
        .generate_encoded_master_key()
    )

    paths = (
        journey
        .prepare_authoritative_runtime_substrate(
            control_plane_root=(
                control_plane_root
            ),
            encoded_master_key=(
                encoded_master_key
            ),
        )
    )

    assert set(
        paths
    ) == {
        "deployment_registry",
        "deployment_secret_store",
        "identity_registry",
        "access_credential_registry",
        "entitlement_registry",
        "account_binding_store",
    }

    for path in paths.values():
        assert path.is_file()

    deployment_registry = (
        journey.CustomerDeploymentRegistry(
            paths[
                "deployment_registry"
            ]
        )
    )

    assert deployment_registry.is_ready()
    assert deployment_registry.size() == 0

    identity_registry = (
        journey.CustomerIdentityRegistry(
            paths[
                "identity_registry"
            ]
        )
    )

    assert identity_registry.is_ready()
    assert identity_registry.size() == 0

    access_registry = (
        journey.CustomerAccessCredentialRegistry(
            paths[
                "access_credential_registry"
            ],
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    assert access_registry.is_ready()
    assert access_registry.size() == 0

    entitlement_registry = (
        journey.CustomerDeploymentEntitlementRegistry(
            paths[
                "entitlement_registry"
            ],
            deployment_registry=(
                deployment_registry
            ),
        )
    )

    assert entitlement_registry.is_ready()
    assert entitlement_registry.size() == 0

    account_binding_store = (
        journey.TrustedAgentAccountBindingStore(
            paths[
                "account_binding_store"
            ]
        )
    )

    assert account_binding_store.is_ready()
    assert account_binding_store.size() == 0


def test_complete_runtime_substrate_rejects_repository_local_root(
) -> None:
    with pytest.raises(
        ValueError,
        match="outside the repository",
    ):
        journey.prepare_authoritative_runtime_substrate(
            control_plane_root=(
                journey._repository_root()
                / "control-plane"
            ),
            encoded_master_key=(
                journey.generate_encoded_master_key()
            ),
        )


def test_build_inputs_require_real_directory_and_executable(
    tmp_path,
) -> None:
    mql5_root = (
        tmp_path
        / "MQL5"
    )

    mql5_root.mkdir()

    metaeditor = (
        tmp_path
        / "metaeditor64.exe"
    )

    metaeditor.write_bytes(
        b"MZ"
    )

    assert (
        journey.require_build_inputs(
            platform_mql5_root=(
                mql5_root
            ),
            metaeditor_path=(
                metaeditor
            ),
        )
        == (
            mql5_root.resolve(),
            metaeditor.resolve(),
        )
    )


def test_registration_uses_real_production_path_and_only_request_id(
    monkeypatch,
) -> None:
    observed = {}

    class FakeResponse:
        def raise_for_status(
            self,
        ):
            observed[
                "raised"
            ] = True

        def json(
            self,
        ):
            return {
                "registration_request_id": (
                    "acceptance-registration-001"
                ),
                "customer_id": (
                    "server-issued-customer"
                ),
            }

    def fake_post(
        url,
        *,
        json,
        timeout,
    ):
        observed[
            "url"
        ] = url

        observed[
            "json"
        ] = json

        observed[
            "timeout"
        ] = timeout

        return FakeResponse()

    monkeypatch.setattr(
        journey.httpx,
        "post",
        fake_post,
    )

    customer_id = (
        journey
        .register_customer_over_production_http(
            setup_base_url=(
                "http://127.0.0.1:8123"
            ),
            registration_request_id=(
                "acceptance-registration-001"
            ),
        )
    )

    assert customer_id == (
        "server-issued-customer"
    )

    assert observed[
        "url"
    ] == (
        "http://127.0.0.1:8123"
        + journey._REGISTRATION_PATH
    )

    assert observed[
        "json"
    ] == {
        "registration_request_id": (
            "acceptance-registration-001"
        ),
    }

    assert observed[
        "timeout"
    ] == 10.0

    assert observed[
        "raised"
    ] is True


def test_registration_rejects_response_request_identity_mismatch(
    monkeypatch,
) -> None:
    class FakeResponse:
        def raise_for_status(
            self,
        ):
            return None

        def json(
            self,
        ):
            return {
                "registration_request_id": (
                    "wrong-request"
                ),
                "customer_id": (
                    "customer"
                ),
            }

    monkeypatch.setattr(
        journey.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(
        RuntimeError,
        match="identity mismatch",
    ):
        (
            journey
            .register_customer_over_production_http(
                setup_base_url=(
                    "http://127.0.0.1:8123"
                ),
                registration_request_id=(
                    "expected-request"
                ),
            )
        )


def test_bootstrap_authorization_uses_authoritative_cli_without_verifier(
    monkeypatch,
) -> None:
    observed = {}

    def fake_run(
        command,
        *,
        cwd,
        env,
        shell,
        check,
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

        observed[
            "check"
        ] = check

    monkeypatch.setattr(
        journey.subprocess,
        "run",
        fake_run,
    )

    environment = {
        "TODOBA_CONTROL_PLANE_DATA_ROOT": (
            "isolated"
        ),
        "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY": (
            "memory-only-key"
        ),
    }

    journey.issue_bootstrap_authorization(
        customer_id=(
            "server-customer"
        ),
        authorization_request_id=(
            "auth-request"
        ),
        code_challenge_s256=(
            "A" * 43
        ),
        environment=environment,
    )

    command = observed[
        "command"
    ]

    assert command[:3] == [
        sys.executable,
        "-m",
        (
            "scripts."
            "issue_customer_setup_bootstrap_authorization"
        ),
    ]

    assert "--customer-id" in command
    assert "server-customer" in command

    assert (
        "--code-challenge-s256"
        in command
    )

    assert (
        "A" * 43
        in command
    )

    assert (
        "--confirm-runtime-stopped"
        in command
    )

    assert (
        "--code-verifier"
        not in command
    )

    assert (
        "--authorization-code"
        not in command
    )

    assert (
        "memory-only-key"
        not in command
    )

    assert observed[
        "env"
    ][
        "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY"
    ] == "memory-only-key"

    assert observed[
        "shell"
    ] is False

    assert observed[
        "check"
    ] is True


def test_package_builder_uses_authoritative_cli_and_child_environment(
    monkeypatch,
    tmp_path,
) -> None:
    mql5_root = (
        tmp_path
        / "MQL5"
    )

    mql5_root.mkdir()

    metaeditor = (
        tmp_path
        / "metaeditor64.exe"
    )

    metaeditor.write_bytes(
        b"MZ"
    )

    workspace = (
        tmp_path
        / "workspace"
    )

    observed = {}

    def fake_run(
        command,
        *,
        cwd,
        env,
        shell,
        check,
    ):
        observed[
            "command"
        ] = command

        observed[
            "env"
        ] = env

        observed[
            "shell"
        ] = shell

        observed[
            "check"
        ] = check

    monkeypatch.setattr(
        journey.subprocess,
        "run",
        fake_run,
    )

    environment = {
        "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY": (
            "memory-only-key"
        ),
    }

    journey.process_package_build_requests(
        platform_mql5_root=(
            mql5_root
        ),
        metaeditor_path=(
            metaeditor
        ),
        workspace_root=(
            workspace
        ),
        environment=environment,
    )

    command = observed[
        "command"
    ]

    assert command[:3] == [
        sys.executable,
        "-m",
        (
            "scripts."
            "process_customer_deployment_package_build_requests"
        ),
    ]

    assert (
        "--platform-mql5-root"
        in command
    )

    assert (
        "--metaeditor-path"
        in command
    )

    assert (
        "--workspace-root"
        in command
    )

    assert (
        "memory-only-key"
        not in command
    )

    assert observed[
        "env"
    ][
        "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY"
    ] == "memory-only-key"

    assert observed[
        "shell"
    ] is False

    assert observed[
        "check"
    ] is True


def test_frozen_installation_requires_exact_published_bytes(
    tmp_path,
) -> None:
    package_root = (
        tmp_path
        / "packages"
    )

    published = (
        package_root
        / "deployment"
        / "TODOBA_Trusted_Agent.ex5"
    )

    published.parent.mkdir(
        parents=True
    )

    artifact = (
        b"trusted-agent-acceptance-artifact"
    )

    published.write_bytes(
        artifact
    )

    mql5_root = (
        tmp_path
        / "terminal"
        / "MQL5"
    )

    experts = (
        mql5_root
        / "Experts"
    )

    experts.mkdir(
        parents=True
    )

    installed = (
        experts
        / published.name
    )

    installed.write_bytes(
        artifact
    )

    (
        result_published,
        result_installed,
        digest,
        size,
    ) = (
        journey
        .verify_frozen_installation(
            platform_mql5_root=(
                mql5_root
            ),
            package_root=(
                package_root
            ),
        )
    )

    assert (
        result_published
        == published.resolve()
    )

    assert (
        result_installed
        == installed.resolve()
    )

    assert size == len(
        artifact
    )

    assert digest == (
        journey.hashlib.sha256(
            artifact
        )
        .hexdigest()
        .upper()
    )


def test_frozen_installation_rejects_hash_mismatch(
    tmp_path,
) -> None:
    package_root = (
        tmp_path
        / "packages"
        / "deployment"
    )

    package_root.mkdir(
        parents=True
    )

    published = (
        package_root
        / "TODOBA_Trusted_Agent.ex5"
    )

    published.write_bytes(
        b"published"
    )

    mql5_root = (
        tmp_path
        / "MQL5"
    )

    experts = (
        mql5_root
        / "Experts"
    )

    experts.mkdir(
        parents=True
    )

    (
        experts
        / published.name
    ).write_bytes(
        b"installed"
    )

    with pytest.raises(
        RuntimeError,
        match="SHA-256|size",
    ):
        journey.verify_frozen_installation(
            platform_mql5_root=(
                mql5_root
            ),
            package_root=(
                package_root.parent
            ),
        )


def test_frozen_installation_requires_exactly_one_published_ex5(
    tmp_path,
) -> None:
    package_root = (
        tmp_path
        / "packages"
    )

    package_root.mkdir()

    mql5_root = (
        tmp_path
        / "MQL5"
    )

    mql5_root.mkdir()

    with pytest.raises(
        RuntimeError,
        match="exactly one published EX5",
    ):
        journey.verify_frozen_installation(
            platform_mql5_root=(
                mql5_root
            ),
            package_root=(
                package_root
            ),
        )


def test_wait_for_process_exit_allows_graceful_shutdown(
) -> None:
    observed = {
        "timeout": None,
        "terminate": 0,
        "kill": 0,
    }

    class GracefulProcess(
        subprocess.Popen
    ):
        def __init__(
            self,
        ):
            pass

        def wait(
            self,
            timeout=None,
        ):
            observed[
                "timeout"
            ] = timeout

            return 0

        def terminate(
            self,
        ):
            observed[
                "terminate"
            ] += 1

        def kill(
            self,
        ):
            observed[
                "kill"
            ] += 1

    result = (
        journey
        ._wait_for_process_exit(
            process=GracefulProcess(),
            name="Frozen customer Setup",
            timeout_seconds=5.0,
        )
    )

    assert result == 0

    assert observed[
        "timeout"
    ] == 5.0

    assert observed[
        "terminate"
    ] == 0

    assert observed[
        "kill"
    ] == 0


def test_wait_for_process_exit_fails_closed_without_killing(
) -> None:
    observed = {
        "terminate": 0,
        "kill": 0,
    }

    class SlowProcess(
        subprocess.Popen
    ):
        def __init__(
            self,
        ):
            pass

        def wait(
            self,
            timeout=None,
        ):
            raise subprocess.TimeoutExpired(
                cmd="TODOBA Trading AI Setup.exe",
                timeout=timeout,
            )

        def terminate(
            self,
        ):
            observed[
                "terminate"
            ] += 1

        def kill(
            self,
        ):
            observed[
                "kill"
            ] += 1

    with pytest.raises(
        RuntimeError,
        match="did not exit within 5.0 seconds",
    ):
        journey._wait_for_process_exit(
            process=SlowProcess(),
            name="Frozen customer Setup",
            timeout_seconds=5.0,
        )

    assert observed[
        "terminate"
    ] == 0

    assert observed[
        "kill"
    ] == 0


def test_real_journey_preserves_security_order(
    monkeypatch,
    tmp_path,
) -> None:
    mql5_root = (
        tmp_path
        / "platform"
        / "MQL5"
    )

    mql5_root.mkdir(
        parents=True
    )

    metaeditor = (
        tmp_path
        / "platform"
        / "metaeditor64.exe"
    )

    metaeditor.write_bytes(
        b"MZ"
    )

    acceptance_root = (
        tmp_path
        / "acceptance"
    )

    fake_executable = (
        tmp_path
        / "TODOBA Trading AI Setup.exe"
    )

    fake_executable.write_bytes(
        b"MZ"
    )

    calls = []

    class FakeProcess(
        subprocess.Popen
    ):
        def __init__(
            self,
            name,
        ):
            self.name = name
            self.closed = False

        def poll(
            self,
        ):
            if self.closed:
                return 0

            return None

        def terminate(
            self,
        ):
            self.closed = True

        def wait(
            self,
            timeout=None,
        ):
            self.closed = True
            return 0

        def kill(
            self,
        ):
            self.closed = True

    servers = []

    def fake_start_server(
        *,
        port,
        environment,
    ):
        process = FakeProcess(
            f"server-{len(servers) + 1}"
        )

        servers.append(
            process
        )

        calls.append(
            "server-start"
        )

        return process

    def fake_wait_server(
        *,
        process,
        port,
    ):
        calls.append(
            "server-ready"
        )

    def fake_stop_server(
        *,
        process,
        timeout_seconds=10.0,
    ):
        calls.append(
            "server-stop"
        )

        process.closed = True

    setup_process = FakeProcess(
        "setup"
    )

    def fake_launch_setup(
        **kwargs,
    ):
        calls.append(
            "frozen-launch"
        )

        return setup_process

    def fake_register(
        **kwargs,
    ):
        calls.append(
            "registration-http"
        )

        return (
            "server-issued-customer"
        )

    def fake_issue(
        **kwargs,
    ):
        calls.append(
            "authorization-issue"
        )

    def fake_build(
        **kwargs,
    ):
        calls.append(
            "package-build"
        )

    fake_published = (
        tmp_path
        / "packages"
        / "deployment"
        / "TODOBA_Trusted_Agent.ex5"
    )

    fake_installed = (
        mql5_root
        / "Experts"
        / "TODOBA_Trusted_Agent.ex5"
    )

    def fake_verify_installation(
        **kwargs,
    ):
        calls.append(
            "install-verify"
        )

        return (
            fake_published,
            fake_installed,
            "A" * 64,
            75168,
        )

    monkeypatch.setattr(
        journey,
        "require_locked_frozen_executable",
        lambda: (
            fake_executable,
            journey._EXPECTED_FROZEN_EXE_SHA256,
        ),
    )

    monkeypatch.setattr(
        journey,
        "prepare_authoritative_runtime_substrate",
        lambda **kwargs: calls.append(
            "runtime-substrate"
        ),
    )

    monkeypatch.setattr(
        journey,
        "prepare_isolated_control_plane",
        lambda **kwargs: calls.append(
            "control-plane-provision"
        ),
    )

    monkeypatch.setattr(
        journey,
        "build_server_environment",
        lambda **kwargs: {
            "ISOLATED": "1",
        },
    )

    monkeypatch.setattr(
        journey,
        "generate_encoded_master_key",
        lambda: "memory-only-master-key",
    )

    monkeypatch.setattr(
        journey,
        "start_production_server",
        fake_start_server,
    )

    monkeypatch.setattr(
        journey,
        "wait_for_server_ready",
        fake_wait_server,
    )

    monkeypatch.setattr(
        journey,
        "stop_production_server",
        fake_stop_server,
    )

    monkeypatch.setattr(
        journey,
        "launch_frozen_customer_setup",
        fake_launch_setup,
    )

    monkeypatch.setattr(
        journey,
        "register_customer_over_production_http",
        fake_register,
    )

    monkeypatch.setattr(
        journey,
        "issue_bootstrap_authorization",
        fake_issue,
    )

    monkeypatch.setattr(
        journey,
        "process_package_build_requests",
        fake_build,
    )

    monkeypatch.setattr(
        journey,
        "verify_frozen_installation",
        fake_verify_installation,
    )

    answers = iter(
        [
            "A" * 43,
            "",
            "",
        ]
    )

    def fake_input(
        prompt,
    ):
        answer = next(
            answers
        )

        if (
            "After the frozen Setup window"
            in prompt
        ):
            setup_process.closed = True

        return answer

    monkeypatch.setattr(
        "builtins.input",
        fake_input,
    )

    result = (
        journey
        .run_operator_assisted_frozen_journey(
            acceptance_root=(
                acceptance_root
            ),
            registration_request_id=(
                "registration-request"
            ),
            authorization_request_id=(
                "authorization-request"
            ),
            platform_mql5_root=(
                mql5_root
            ),
            metaeditor_path=(
                metaeditor
            ),
            port=8123,
        )
    )

    assert result.customer_id == (
        "server-issued-customer"
    )

    assert (
        result.published_artifact_path
        == fake_published
    )

    assert (
        result.installed_artifact_path
        == fake_installed
    )

    assert (
        result.installed_artifact_sha256
        == "A" * 64
    )

    assert (
        result.installed_artifact_size_bytes
        == 75168
    )

    assert calls == [
        "runtime-substrate",
        "control-plane-provision",
        "server-start",
        "server-ready",
        "registration-http",
        "server-stop",
        "frozen-launch",
        "authorization-issue",
        "server-start",
        "server-ready",
        "server-stop",
        "package-build",
        "server-start",
        "server-ready",
        "server-stop",
        "install-verify",
    ]

    assert (
        calls.index(
            "registration-http"
        )
        < calls.index(
            "authorization-issue"
        )
    )

    assert (
        calls.index(
            "frozen-launch"
        )
        < calls.index(
            "authorization-issue"
        )
    )

    assert (
        calls.index(
            "authorization-issue"
        )
        < calls.index(
            "package-build"
        )
    )


def test_operator_owner_has_no_direct_durable_business_write_authority(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_frozen_journey.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "CustomerRegistrationStore",
        "CustomerRegistrationService",
        "CustomerSetupBootstrapAuthorizationService",
        "CustomerSetupActivationService",
        "CustomerSetupHandoffService",
        "CustomerDeploymentPackageBuildWorker",
        "CustomerDeploymentPackagePublication",
    )

    for token in forbidden:
        assert token not in source

    tree = ast.parse(
        source
    )

    called_attributes = [
        node.func.attr
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
        )
    ]

    assert (
        called_attributes.count(
            "initialize_empty"
        )
        == 1
    )

    assert (
        "register"
        not in called_attributes
    )


def test_operator_owner_has_no_authorization_code_or_verifier_input_surface(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_frozen_journey.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    forbidden_parameters = {
        "authorization_code",
        "code_verifier",
        "setup_launch_credential",
        "handoff_credential",
        "continuation_credential",
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
            forbidden_parameters
            .isdisjoint(
                parameters
            )
        )


def test_production_registration_contract_remains_server_issued_customer_id(
) -> None:
    assert (
        journey._REGISTRATION_PATH
        == "/customer/register"
    )


def test_operator_owner_uses_authoritative_boundary_owners(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_frozen_journey.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    required = (
        "launch_frozen_customer_setup",
        "prepare_isolated_control_plane",
        "start_production_server",
        "stop_production_server",
        "issue_customer_setup_bootstrap_authorization",
        "process_customer_deployment_package_build_requests",
        "_REGISTRATION_PATH",
    )

    for token in required:
        assert token in source


def test_master_key_is_not_a_cli_argument(
) -> None:
    source_path = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "scripts"
        / "customer_setup_windows_frozen_journey.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "--master-key"
        not in source
    )

    assert (
        "--encoded-master-key"
        not in source
    )


def test_post_g3_harness_locks_continue_finish_and_rebuilt_binary(
) -> None:
    assert (
        journey._EXPECTED_FROZEN_EXE_SHA256
        == (
            "B302241F4CB1FB900DE7B0FB245C8785"
            "184388621DA6460E745F33DAD1153A99"
        )
    )

    source_path = (
        journey.Path(
            journey.__file__
        )
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "explicit customer Continue"
        in source
    )

    assert (
        "EXPLICIT CONTINUE + INSTALL + FINISH"
        in source
    )

    assert (
        "Click the explicit Continue action "
        "in the frozen Setup."
        in source
    )

    assert (
        "When Finish is enabled, click Finish "
        "and wait for the TODOBA Trading AI "
        "Setup window to close."
        in source
    )

    assert (
        "After you click Finish and the "
        "frozen Setup window closes, "
        "press Enter here: "
        in source
    )

    forbidden = (
        "explicit customer Retry",
        "EXPLICIT RETRY + INSTALL",
        "Click the explicit Retry",
        "After Setup reaches Finish, close the ",
    )

    for value in forbidden:
        assert value not in source


def test_real_journey_does_not_force_terminate_frozen_setup(
) -> None:
    import ast
    import inspect
    import textwrap

    source = textwrap.dedent(
        inspect.getsource(
            journey.run_operator_assisted_frozen_journey
        )
    )

    tree = ast.parse(
        source
    )

    natural_exit_calls = []

    forbidden_calls = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        func = node.func

        if (
            isinstance(func, ast.Name)
            and func.id == "_wait_for_process_exit"
        ):
            process_keywords = [
                keyword.value
                for keyword in node.keywords
                if keyword.arg == "process"
            ]

            if (
                len(process_keywords) == 1
                and isinstance(
                    process_keywords[0],
                    ast.Name,
                )
                and process_keywords[0].id
                == "setup_process"
            ):
                natural_exit_calls.append(
                    node
                )

        if (
            isinstance(func, ast.Name)
            and func.id
            == "_terminate_process_safely"
        ):
            forbidden_calls.append(
                "_terminate_process_safely"
            )

        if (
            isinstance(func, ast.Attribute)
            and func.attr in {
                "terminate",
                "kill",
            }
        ):
            try:
                receiver = ast.unparse(
                    func.value
                )
            except Exception:
                receiver = ""

            if "setup_process" in receiver:
                forbidden_calls.append(
                    func.attr
                )

    assert len(
        natural_exit_calls
    ) == 1

    assert forbidden_calls == []
