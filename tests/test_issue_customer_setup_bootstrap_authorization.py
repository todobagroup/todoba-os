"""
Owner tests for the TODOBA operator bootstrap
authorization issuance boundary.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

import scripts.issue_customer_setup_bootstrap_authorization as issue_module


AUTHORIZATION_REQUEST_ID = (
    "setup-auth-request-001"
)

CUSTOMER_ID = (
    "customer-001"
)

CODE_CHALLENGE = (
    "A" * 43
)

AUTHORIZATION_CODE = (
    "tdbba."
    + ("1" * 32)
    + "."
    + ("B" * 43)
)

ISSUED_AT = (
    "2026-08-31T05:30:00.000000Z"
)

EXPIRES_AT = (
    "2026-08-31T05:35:00.000000Z"
)

CURRENT_TIME = datetime(
    2026,
    8,
    31,
    5,
    30,
    tzinfo=timezone.utc,
)


class FakeIssuance:
    def __init__(
        self,
        *,
        authorization_code=AUTHORIZATION_CODE,
        expires_at=EXPIRES_AT,
    ):
        self.authorization_code = (
            authorization_code
        )
        self.expires_at = (
            expires_at
        )


def _main_args():
    return [
        "--authorization-request-id",
        AUTHORIZATION_REQUEST_ID,
        "--customer-id",
        CUSTOMER_ID,
        "--code-challenge-s256",
        CODE_CHALLENGE,
        "--confirm-runtime-stopped",
    ]


def test_parser_requires_exact_operator_inputs(
) -> None:
    parser = issue_module._build_parser()

    arguments = parser.parse_args(
        _main_args()
    )

    assert (
        arguments.authorization_request_id
        == AUTHORIZATION_REQUEST_ID
    )
    assert (
        arguments.customer_id
        == CUSTOMER_ID
    )
    assert (
        arguments.code_challenge_s256
        == CODE_CHALLENGE
    )
    assert (
        arguments.confirm_runtime_stopped
        is True
    )


def test_runtime_stopped_confirmation_is_required(
) -> None:
    parser = issue_module._build_parser()

    with pytest.raises(
        SystemExit,
    ):
        parser.parse_args(
            [
                "--authorization-request-id",
                AUTHORIZATION_REQUEST_ID,
                "--customer-id",
                CUSTOMER_ID,
                "--code-challenge-s256",
                CODE_CHALLENGE,
            ]
        )


def test_parser_exposes_no_code_verifier_input(
) -> None:
    parser = issue_module._build_parser()

    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }

    assert (
        "--code-verifier"
        not in option_strings
    )


def test_parser_exposes_no_business_deployment_inputs(
) -> None:
    parser = issue_module._build_parser()

    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }

    forbidden = {
        "--deployment-id",
        "--agent-id",
        "--account-fingerprint",
        "--setup-activation-id",
        "--payment-id",
        "--subscription-id",
        "--setup-launch-credential",
        "--handoff-credential",
    }

    assert forbidden.isdisjoint(
        option_strings
    )


def test_compose_uses_authoritative_customer_identity_path(
    monkeypatch,
    tmp_path,
) -> None:
    observed = {}

    class FakeIdentityRegistry:
        def __init__(
            self,
            storage_path,
        ):
            observed[
                "identity_path"
            ] = storage_path

        def is_ready(
            self,
        ):
            return True

    class FakeAuthorizationStore:
        def __init__(
            self,
            storage_path,
            *,
            customer_identity_registry,
        ):
            observed[
                "authorization_path"
            ] = storage_path
            observed[
                "store_identity_registry"
            ] = customer_identity_registry

        def open_existing(
            self,
        ):
            observed[
                "open_existing"
            ] = (
                observed.get(
                    "open_existing",
                    0,
                )
                + 1
            )

        def is_ready(
            self,
        ):
            return True

    class FakeService:
        def __init__(
            self,
            *,
            authorization_store,
            customer_identity_registry,
        ):
            observed[
                "service_store"
            ] = authorization_store
            observed[
                "service_identity_registry"
            ] = customer_identity_registry

    monkeypatch.setattr(
        issue_module,
        "CustomerIdentityRegistry",
        FakeIdentityRegistry,
    )
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationStore",
        FakeAuthorizationStore,
    )
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationService",
        FakeService,
    )

    result = (
        issue_module._compose_issuance_service(
            control_plane_root=tmp_path,
        )
    )

    assert isinstance(
        result,
        FakeService,
    )

    assert observed[
        "identity_path"
    ] == (
        tmp_path
        / "commercial"
        / "customer_identities.json"
    )

    assert observed[
        "authorization_path"
    ] == (
        tmp_path
        / "commercial"
        / (
            "customer_setup_bootstrap_"
            "authorizations.json"
        )
    )

    assert (
        observed[
            "store_identity_registry"
        ]
        is
        observed[
            "service_identity_registry"
        ]
    )

    assert observed[
        "open_existing"
    ] == 1


def test_identity_registry_must_already_be_ready(
    monkeypatch,
    tmp_path,
) -> None:
    store_calls = []

    class NotReadyIdentityRegistry:
        def __init__(
            self,
            storage_path,
        ):
            del storage_path

        def is_ready(
            self,
        ):
            return False

    class ForbiddenStore:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            store_calls.append(
                (
                    args,
                    kwargs,
                )
            )

    monkeypatch.setattr(
        issue_module,
        "CustomerIdentityRegistry",
        NotReadyIdentityRegistry,
    )
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationStore",
        ForbiddenStore,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "identity registry is not provisioned"
        ),
    ):
        issue_module._compose_issuance_service(
            control_plane_root=tmp_path,
        )

    assert store_calls == []


def test_authorization_store_is_opened_existing_only(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    class FakeIdentityRegistry:
        def __init__(
            self,
            storage_path,
        ):
            del storage_path

        def is_ready(
            self,
        ):
            return True

    class FakeAuthorizationStore:
        def __init__(
            self,
            storage_path,
            *,
            customer_identity_registry,
        ):
            del storage_path
            del customer_identity_registry

        def open_existing(
            self,
        ):
            calls.append(
                "open_existing"
            )

        def is_ready(
            self,
        ):
            calls.append(
                "is_ready"
            )
            return True

    class FakeService:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs
            calls.append(
                "service"
            )

    monkeypatch.setattr(
        issue_module,
        "CustomerIdentityRegistry",
        FakeIdentityRegistry,
    )
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationStore",
        FakeAuthorizationStore,
    )
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationService",
        FakeService,
    )

    issue_module._compose_issuance_service(
        control_plane_root=tmp_path,
    )

    assert calls == [
        "open_existing",
        "is_ready",
        "service",
    ]


def test_not_ready_authorization_store_fails_closed(
    monkeypatch,
    tmp_path,
) -> None:
    service_calls = []

    class FakeIdentityRegistry:
        def __init__(
            self,
            storage_path,
        ):
            del storage_path

        def is_ready(
            self,
        ):
            return True

    class NotReadyStore:
        def __init__(
            self,
            storage_path,
            *,
            customer_identity_registry,
        ):
            del storage_path
            del customer_identity_registry

        def open_existing(
            self,
        ):
            return None

        def is_ready(
            self,
        ):
            return False

    class ForbiddenService:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            service_calls.append(
                (
                    args,
                    kwargs,
                )
            )

    monkeypatch.setattr(
        issue_module,
        "CustomerIdentityRegistry",
        FakeIdentityRegistry,
    )
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationStore",
        NotReadyStore,
    )
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationService",
        ForbiddenService,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "authorization store is not ready"
        ),
    ):
        issue_module._compose_issuance_service(
            control_plane_root=tmp_path,
        )

    assert service_calls == []


def test_main_passes_exact_operator_material_to_issue(
    monkeypatch,
    capsys,
) -> None:
    observed = {}

    class FakeService:
        def issue(
            self,
            **kwargs,
        ):
            observed.update(
                kwargs
            )
            return FakeIssuance()

    monkeypatch.setattr(
        issue_module,
        "_compose_issuance_service",
        lambda **kwargs: (
            observed.setdefault(
                "composition",
                kwargs,
            )
            and FakeService()
        ),
    )

    monkeypatch.setattr(
        issue_module,
        "_utc_now",
        lambda: CURRENT_TIME,
    )

    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationIssuance",
        FakeIssuance,
    )

    issue_module.main(
        _main_args()
    )

    capsys.readouterr()

    assert observed[
        "authorization_request_id"
    ] == AUTHORIZATION_REQUEST_ID

    assert observed[
        "customer_id"
    ] == CUSTOMER_ID

    assert observed[
        "code_challenge_s256"
    ] == CODE_CHALLENGE

    assert observed[
        "current_time"
    ] == CURRENT_TIME


def test_main_uses_configured_control_plane_root(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    observed = {}

    class FakeService:
        def issue(
            self,
            **kwargs,
        ):
            del kwargs
            return FakeIssuance()

    monkeypatch.setattr(
        issue_module,
        "TODOBA_CONTROL_PLANE_DATA_ROOT",
        tmp_path,
    )

    def compose(
        *,
        control_plane_root,
    ):
        observed[
            "root"
        ] = control_plane_root
        return FakeService()

    monkeypatch.setattr(
        issue_module,
        "_compose_issuance_service",
        compose,
    )
    monkeypatch.setattr(
        issue_module,
        "_utc_now",
        lambda: CURRENT_TIME,
    )
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationIssuance",
        FakeIssuance,
    )

    issue_module.main(
        _main_args()
    )

    capsys.readouterr()

    assert observed[
        "root"
    ] == tmp_path


def test_main_does_not_pass_code_verifier(
    monkeypatch,
    capsys,
) -> None:
    observed = {}

    class FakeService:
        def issue(
            self,
            **kwargs,
        ):
            observed.update(
                kwargs
            )
            return FakeIssuance()

    monkeypatch.setattr(
        issue_module,
        "_compose_issuance_service",
        lambda **kwargs: FakeService(),
    )
    monkeypatch.setattr(
        issue_module,
        "_utc_now",
        lambda: CURRENT_TIME,
    )
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationIssuance",
        FakeIssuance,
    )

    issue_module.main(
        _main_args()
    )

    capsys.readouterr()

    assert (
        "code_verifier"
        not in observed
    )


def test_service_failure_propagates_without_result_output(
    monkeypatch,
    capsys,
) -> None:
    class FailingService:
        def issue(
            self,
            **kwargs,
        ):
            del kwargs

            raise ValueError(
                "Unknown customer identity."
            )

    monkeypatch.setattr(
        issue_module,
        "_compose_issuance_service",
        lambda **kwargs: FailingService(),
    )
    monkeypatch.setattr(
        issue_module,
        "_utc_now",
        lambda: CURRENT_TIME,
    )

    with pytest.raises(
        ValueError,
        match="Unknown customer identity",
    ):
        issue_module.main(
            _main_args()
        )

    captured = capsys.readouterr()

    assert (
        AUTHORIZATION_CODE
        not in captured.out
    )


def test_invalid_issue_result_fails_closed(
    monkeypatch,
    capsys,
) -> None:
    class FakeService:
        def issue(
            self,
            **kwargs,
        ):
            del kwargs
            return object()

    monkeypatch.setattr(
        issue_module,
        "_compose_issuance_service",
        lambda **kwargs: FakeService(),
    )
    monkeypatch.setattr(
        issue_module,
        "_utc_now",
        lambda: CURRENT_TIME,
    )

    with pytest.raises(
        RuntimeError,
        match="invalid result",
    ):
        issue_module.main(
            _main_args()
        )

    captured = capsys.readouterr()

    assert (
        AUTHORIZATION_CODE
        not in captured.out
    )


def test_safe_output_prints_authorization_code_exactly_once(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationIssuance",
        FakeIssuance,
    )

    issue_module._print_safe_result(
        FakeIssuance()
    )

    output = (
        capsys.readouterr().out
    )

    assert (
        output.count(
            AUTHORIZATION_CODE
        )
        == 1
    )

    assert EXPIRES_AT in output


def test_safe_output_does_not_print_customer_identity(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        issue_module,
        "CustomerSetupBootstrapAuthorizationIssuance",
        FakeIssuance,
    )

    issue_module._print_safe_result(
        FakeIssuance()
    )

    output = (
        capsys.readouterr().out
    )

    assert CUSTOMER_ID not in output
    assert (
        AUTHORIZATION_REQUEST_ID
        not in output
    )
    assert CODE_CHALLENGE not in output


def test_owner_has_no_http_or_server_authority(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / (
            "issue_customer_setup_"
            "bootstrap_authorization.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_roots = set()

    for node in ast.walk(tree):
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

        if isinstance(
            node,
            ast.ImportFrom,
        ) and node.module:
            imported_roots.add(
                node.module.split(
                    ".",
                    1,
                )[0]
            )

    assert {
        "fastapi",
        "httpx",
        "requests",
        "uvicorn",
    }.isdisjoint(
        imported_roots
    )

    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
        )
    }

    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.Import,
        )
        for alias in node.names
    )

    assert (
        "backend.main"
        not in imported_modules
    )


def test_owner_imports_only_required_commercial_authorities(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / (
            "issue_customer_setup_"
            "bootstrap_authorization.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    modules = {
        node.module
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
            and node.module.startswith(
                "backend.commercial."
            )
        )
    }

    assert modules == {
        (
            "backend.commercial."
            "customer_identity_registry"
        ),
        (
            "backend.commercial."
            "customer_setup_bootstrap_"
            "authorization_service"
        ),
    }


def test_owner_never_initializes_durable_state(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / (
            "issue_customer_setup_"
            "bootstrap_authorization.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
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
    }

    assert (
        "initialize_empty"
        not in called_attributes
    )

    assert (
        "register"
        not in called_attributes
    )


def test_owner_opens_bootstrap_store_existing(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / (
            "issue_customer_setup_"
            "bootstrap_authorization.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    calls = [
        node
        for node in ast.walk(tree)
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
            == "open_existing"
        )
    ]

    assert len(calls) == 1


def test_owner_has_no_pkce_verifier_or_generation_authority(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / (
            "issue_customer_setup_"
            "bootstrap_authorization.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_roots = set()

    for node in ast.walk(tree):
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

    assert (
        "secrets"
        not in imported_roots
    )

    assert (
        "derive_pkce_s256_code_challenge"
        not in source
    )

    parameters = {
        arg.arg
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.FunctionDef,
        )
        for arg in (
            node.args.posonlyargs
            + node.args.args
            + node.args.kwonlyargs
        )
    }

    assert (
        "code_verifier"
        not in parameters
    )


def test_owner_has_no_deployment_or_activation_authority(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / (
            "issue_customer_setup_"
            "bootstrap_authorization.py"
        )
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "CustomerDeployment",
        "CustomerOnboardingService",
        "CustomerSetupActivationService",
        "CustomerSetupLaunchCredentialService",
        "CustomerSetupBootstrapLaunchGrantService",
        "CustomerSetupLauncher",
        "account_fingerprint",
        "deployment_id",
        "agent_id",
        "payment_id",
        "subscription_id",
    )

    for token in forbidden:
        assert token not in source


def test_main_accepts_only_argv_parameter(
) -> None:
    import inspect

    parameters = set(
        inspect.signature(
            issue_module.main
        ).parameters
    )

    assert parameters == {
        "argv",
    }


def test_utc_now_is_timezone_aware(
) -> None:
    value = issue_module._utc_now()

    assert value.tzinfo is not None
    assert (
        value.utcoffset()
        is not None
    )
