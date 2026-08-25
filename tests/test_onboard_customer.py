import ast
import base64
from pathlib import Path

import pytest

from backend.commercial.customer_onboarding_service import (
    CustomerOnboardingResult,
    CustomerOnboardingService,
)
import scripts.onboard_customer as cli


REQUEST_ID = "onboarding-request-001"
CUSTOMER_ID = "customer-001"
ACCOUNT_FINGERPRINT = (
    "XMGlobal-MT5-6:account-001"
)

ACCESS_CREDENTIAL = (
    "tdbca1.credential-001."
    "one-time-secret"
)


def encoded_master_key() -> str:
    return (
        base64.urlsafe_b64encode(
            b"K" * 32
        )
        .decode(
            "ascii"
        )
    )


def make_result(
    *,
    request_id: str = REQUEST_ID,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str = "deployment-001",
    agent_id: str = "trusted-agent-001",
    credential_id: str = "credential-001",
    access_credential: str = ACCESS_CREDENTIAL,
) -> CustomerOnboardingResult:
    return CustomerOnboardingResult(
        onboarding_request_id=request_id,
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
        credential_id=credential_id,
        access_credential=access_credential,
        artifact_sha256="a" * 64,
        artifact_size_bytes=123,
    )


class InitializationProbe:
    def __init__(
        self,
        *,
        ready: bool,
    ) -> None:
        self.ready = ready
        self.initialize_count = 0

    def is_ready(
        self,
    ) -> bool:
        return self.ready

    def initialize_empty(
        self,
    ) -> None:
        self.initialize_count += 1
        self.ready = True


class StubOnboardingService:
    def __init__(
        self,
        *,
        results: list[
            CustomerOnboardingResult
        ],
    ) -> None:
        self.results = list(
            results
        )

        self.calls: list[
            tuple[str, str, str]
        ] = []

    def onboard(
        self,
        *,
        onboarding_request_id: str,
        customer_id: str,
        account_fingerprint: str,
    ) -> CustomerOnboardingResult:
        self.calls.append(
            (
                onboarding_request_id,
                customer_id,
                account_fingerprint,
            )
        )

        if not self.results:
            raise AssertionError(
                "No onboarding result configured."
            )

        return self.results.pop(
            0
        )


def required_cli_arguments() -> list[str]:
    return [
        "--onboarding-request-id",
        REQUEST_ID,
        "--customer-id",
        CUSTOMER_ID,
        "--account-fingerprint",
        ACCOUNT_FINGERPRINT,
        "--platform-mql5-root",
        "C:/MT5/MQL5",
        "--metaeditor-path",
        "C:/MT5/MetaEditor64.exe",
        "--workspace-root",
        "C:/TODOBA-BUILD",
        "--confirm-runtime-stopped",
    ]


def test_initialize_if_missing_initializes_missing_owner(
) -> None:
    owner = InitializationProbe(
        ready=False
    )

    cli._initialize_if_missing(
        owner
    )

    assert owner.ready is True

    assert (
        owner.initialize_count
        == 1
    )


def test_initialize_if_missing_preserves_ready_owner(
) -> None:
    owner = InitializationProbe(
        ready=True
    )

    cli._initialize_if_missing(
        owner
    )

    assert owner.ready is True

    assert (
        owner.initialize_count
        == 0
    )


def test_compose_customer_onboarding_service_uses_isolated_control_plane(
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    trading_root = (
        control_plane_root
        / "trading"
    )

    commercial_root.mkdir(
        parents=True
    )

    trading_root.mkdir(
        parents=True
    )

    repository_root = (
        tmp_path
        / "repository"
    )

    mql5_source_root = (
        repository_root
        / "MQL5"
    )

    platform_mql5_root = (
        tmp_path
        / "platform"
        / "MQL5"
    )

    workspace_root = (
        tmp_path
        / "workspace"
    )

    package_root = (
        tmp_path
        / "packages"
    )

    for directory in (
        mql5_source_root,
        platform_mql5_root,
        workspace_root,
        package_root,
    ):
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    metaeditor_path = (
        tmp_path
        / "MetaEditor64.exe"
    )

    metaeditor_path.write_bytes(
        b"TEST-METAEDITOR-NOT-EXECUTED"
    )

    service = (
        cli._compose_customer_onboarding_service(
            control_plane_root=(
                control_plane_root
            ),
            encoded_master_key=(
                encoded_master_key()
            ),
            mql5_source_root=(
                mql5_source_root
            ),
            platform_mql5_root=(
                platform_mql5_root
            ),
            workspace_root=(
                workspace_root
            ),
            package_root=(
                package_root
            ),
            metaeditor_path=(
                metaeditor_path
            ),
        )
    )

    assert isinstance(
        service,
        CustomerOnboardingService,
    )

    expected_control_plane_files = {
        (
            commercial_root
            / "customer_deployments.json"
        ),
        (
            commercial_root
            / "customer_deployment_secrets.json"
        ),
        (
            commercial_root
            / "customer_deployment_bootstraps.json"
        ),
        (
            commercial_root
            / "customer_identities.json"
        ),
        (
            commercial_root
            / "customer_access_credentials.json"
        ),
        (
            commercial_root
            / "customer_deployment_entitlements.json"
        ),
        (
            commercial_root
            / "customer_access_provisioning.json"
        ),
        (
            trading_root
            / "trusted_agent_account_bindings.json"
        ),
    }

    for expected_path in (
        expected_control_plane_files
    ):
        assert (
            expected_path.is_file()
        )

    assert not list(
        package_root.rglob(
            "*.ex5"
        )
    )

    assert not list(
        workspace_root.iterdir()
    )


def test_invalid_master_key_fails_before_durable_initialization(
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    trading_root = (
        control_plane_root
        / "trading"
    )

    commercial_root.mkdir(
        parents=True
    )

    trading_root.mkdir(
        parents=True
    )

    directories = {
        "mql5_source_root": (
            tmp_path
            / "source"
        ),
        "platform_mql5_root": (
            tmp_path
            / "platform"
        ),
        "workspace_root": (
            tmp_path
            / "workspace"
        ),
        "package_root": (
            tmp_path
            / "package"
        ),
    }

    for directory in (
        directories.values()
    ):
        directory.mkdir(
            parents=True
        )

    metaeditor_path = (
        tmp_path
        / "MetaEditor64.exe"
    )

    metaeditor_path.write_bytes(
        b"NOT-EXECUTED"
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY"
        ),
    ):
        cli._compose_customer_onboarding_service(
            control_plane_root=(
                control_plane_root
            ),
            encoded_master_key=(
                "invalid key"
            ),
            mql5_source_root=(
                directories[
                    "mql5_source_root"
                ]
            ),
            platform_mql5_root=(
                directories[
                    "platform_mql5_root"
                ]
            ),
            workspace_root=(
                directories[
                    "workspace_root"
                ]
            ),
            package_root=(
                directories[
                    "package_root"
                ]
            ),
            metaeditor_path=(
                metaeditor_path
            ),
        )

    assert not list(
        commercial_root.iterdir()
    )

    assert not list(
        trading_root.iterdir()
    )


@pytest.mark.parametrize(
    "argument_name",
    [
        "control_plane_root",
        "mql5_source_root",
        "platform_mql5_root",
        "workspace_root",
        "package_root",
        "metaeditor_path",
    ],
)
def test_composition_requires_path_inputs(
    tmp_path: Path,
    argument_name: str,
) -> None:
    values = {
        "control_plane_root": (
            tmp_path
            / "control"
        ),
        "encoded_master_key": (
            encoded_master_key()
        ),
        "mql5_source_root": (
            tmp_path
            / "source"
        ),
        "platform_mql5_root": (
            tmp_path
            / "platform"
        ),
        "workspace_root": (
            tmp_path
            / "workspace"
        ),
        "package_root": (
            tmp_path
            / "package"
        ),
        "metaeditor_path": (
            tmp_path
            / "MetaEditor64.exe"
        ),
    }

    values[
        argument_name
    ] = "not-a-path"

    with pytest.raises(
        TypeError,
        match=(
            f"^{argument_name} "
            "must be Path\\.$"
        ),
    ):
        cli._compose_customer_onboarding_service(
            **values
        )


def test_parser_exposes_exact_operator_arguments(
) -> None:
    parser = (
        cli._build_parser()
    )

    options = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--")
        and option != "--help"
    }

    assert options == {
        "--onboarding-request-id",
        "--customer-id",
        "--account-fingerprint",
        "--platform-mql5-root",
        "--metaeditor-path",
        "--workspace-root",
        "--confirm-runtime-stopped",
    }


def test_parser_does_not_expose_internal_security_arguments(
) -> None:
    parser = (
        cli._build_parser()
    )

    options = {
        option
        for action in parser._actions
        for option in action.option_strings
    }

    assert not (
        {
            "--deployment-id",
            "--agent-id",
            "--credential-id",
            "--access-credential",
            "--agent-secret",
            "--execution-mission-signing-secret",
            "--control-mission-signing-secret",
            "--control-plane-root",
            "--package-root",
            "--master-key",
        }
        & options
    )


def test_runtime_stopped_confirmation_is_required(
) -> None:
    arguments = (
        required_cli_arguments()
    )

    arguments.remove(
        "--confirm-runtime-stopped"
    )

    parser = (
        cli._build_parser()
    )

    with pytest.raises(
        SystemExit,
    ) as error:
        parser.parse_args(
            arguments
        )

    assert error.value.code == 2


def test_main_does_not_compose_without_runtime_stop_confirmation(
    monkeypatch,
) -> None:
    compose_calls = []

    def forbidden_compose(
        **kwargs,
    ):
        compose_calls.append(
            kwargs
        )

        raise AssertionError(
            "Composition must not occur."
        )

    monkeypatch.setattr(
        cli,
        "_compose_customer_onboarding_service",
        forbidden_compose,
    )

    arguments = (
        required_cli_arguments()
    )

    arguments.remove(
        "--confirm-runtime-stopped"
    )

    with pytest.raises(
        SystemExit,
    ):
        cli.main(
            arguments
        )

    assert compose_calls == []


def test_main_uses_authoritative_config_and_delegates_once(
    monkeypatch,
    tmp_path: Path,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    repository_source_root = (
        tmp_path
        / "repository-MQL5"
    )

    package_root = (
        tmp_path
        / "customer-packages"
    )

    configured_master_key = (
        encoded_master_key()
    )

    monkeypatch.setattr(
        cli,
        "TODOBA_CONTROL_PLANE_DATA_ROOT",
        control_plane_root,
    )

    monkeypatch.setattr(
        cli,
        "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY",
        configured_master_key,
    )

    monkeypatch.setattr(
        cli,
        "REPOSITORY_MQL5_SOURCE_ROOT",
        repository_source_root,
    )

    monkeypatch.setattr(
        cli,
        "get_customer_package_root",
        lambda: package_root,
    )

    service = StubOnboardingService(
        results=[
            make_result()
        ]
    )

    composition_calls = []

    def fake_compose(
        **kwargs,
    ):
        composition_calls.append(
            kwargs
        )

        return service

    monkeypatch.setattr(
        cli,
        "_compose_customer_onboarding_service",
        fake_compose,
    )

    cli.main(
        required_cli_arguments()
    )

    assert len(
        composition_calls
    ) == 1

    composed = (
        composition_calls[0]
    )

    assert (
        composed[
            "control_plane_root"
        ]
        == control_plane_root
    )

    assert (
        composed[
            "encoded_master_key"
        ]
        == configured_master_key
    )

    assert (
        composed[
            "mql5_source_root"
        ]
        == repository_source_root
    )

    assert (
        composed[
            "package_root"
        ]
        == package_root
    )

    assert (
        composed[
            "platform_mql5_root"
        ]
        == Path(
            "C:/MT5/MQL5"
        )
    )

    assert (
        composed[
            "metaeditor_path"
        ]
        == Path(
            "C:/MT5/MetaEditor64.exe"
        )
    )

    assert (
        composed[
            "workspace_root"
        ]
        == Path(
            "C:/TODOBA-BUILD"
        )
    )

    assert service.calls == [
        (
            REQUEST_ID,
            CUSTOMER_ID,
            ACCOUNT_FINGERPRINT,
        )
    ]


def test_main_output_contains_one_time_credential_once_and_no_account_fingerprint(
    monkeypatch,
    capsys,
) -> None:
    service = StubOnboardingService(
        results=[
            make_result()
        ]
    )

    monkeypatch.setattr(
        cli,
        "_compose_customer_onboarding_service",
        lambda **kwargs: service,
    )

    monkeypatch.setattr(
        cli,
        "get_customer_package_root",
        lambda: Path(
            "C:/SERVER/PRIVATE/PACKAGES"
        ),
    )

    cli.main(
        required_cli_arguments()
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "TODOBA CUSTOMER ONBOARDING COMPLETED"
        in output
    )

    assert (
        REQUEST_ID
        in output
    )

    assert (
        CUSTOMER_ID
        in output
    )

    assert (
        "deployment-001"
        in output
    )

    assert (
        "trusted-agent-001"
        in output
    )

    assert (
        "credential-001"
        in output
    )

    assert (
        output.count(
            ACCESS_CREDENTIAL
        )
        == 1
    )

    assert (
        ACCOUNT_FINGERPRINT
        not in output
    )

    assert (
        "C:/SERVER/PRIVATE/PACKAGES"
        not in output
    )

    assert (
        "agent_secret"
        not in output
    )

    assert (
        "signing_secret"
        not in output
    )


def test_print_safe_result_rejects_non_owner_result(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "^result must be "
            "CustomerOnboardingResult\\.$"
        ),
    ):
        cli._print_safe_result(
            object()
        )


def test_print_safe_result_exposes_safe_metadata_and_one_credential(
    capsys,
) -> None:
    result = make_result()

    cli._print_safe_result(
        result
    )

    output = (
        capsys
        .readouterr()
        .out
    )

    assert (
        "Onboarding request ID: "
        + REQUEST_ID
        in output
    )

    assert (
        "Customer ID: "
        + CUSTOMER_ID
        in output
    )

    assert (
        "Deployment ID: deployment-001"
        in output
    )

    assert (
        "Agent ID: trusted-agent-001"
        in output
    )

    assert (
        "Credential ID: credential-001"
        in output
    )

    assert (
        "Package SHA256: "
        + ("a" * 64)
        in output
    )

    assert (
        "Package size bytes: 123"
        in output
    )

    assert (
        output.count(
            ACCESS_CREDENTIAL
        )
        == 1
    )


def test_repeated_cli_request_preserves_request_identity(
    monkeypatch,
) -> None:
    service = StubOnboardingService(
        results=[
            make_result(
                access_credential=(
                    "tdbca1.credential-001.secret-one"
                )
            ),
            make_result(
                access_credential=(
                    "tdbca1.credential-001.secret-two"
                )
            ),
        ]
    )

    monkeypatch.setattr(
        cli,
        "_compose_customer_onboarding_service",
        lambda **kwargs: service,
    )

    cli.main(
        required_cli_arguments()
    )

    cli.main(
        required_cli_arguments()
    )

    assert service.calls == [
        (
            REQUEST_ID,
            CUSTOMER_ID,
            ACCOUNT_FINGERPRINT,
        ),
        (
            REQUEST_ID,
            CUSTOMER_ID,
            ACCOUNT_FINGERPRINT,
        ),
    ]


def test_cli_source_does_not_import_cloud_main_or_generate_request_identity(
) -> None:
    path = Path(
        "scripts/onboard_customer.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_modules = []

    for node in tree.body:
        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.extend(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            imported_modules.append(
                node.module or ""
            )

    assert (
        "backend.main"
        not in imported_modules
    )

    forbidden_generation_names = {
        "uuid4",
        "token_hex",
        "token_urlsafe",
        "randint",
    }

    used_names = {
        node.id
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            ast.Name,
        )
    }

    assert not (
        forbidden_generation_names
        & used_names
    )


def test_cli_source_prints_plaintext_access_credential_exactly_once(
) -> None:
    path = Path(
        "scripts/onboard_customer.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    credential_prints = []

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "print"
        ):
            continue

        rendered = (
            ast.get_source_segment(
                source,
                node,
            )
            or ""
        )

        if (
            "access_credential"
            in rendered
        ):
            credential_prints.append(
                rendered
            )

    assert len(
        credential_prints
    ) == 1
