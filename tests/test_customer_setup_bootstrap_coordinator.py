"""
Owner tests for TODOBA Customer Setup Bootstrap Coordinator.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import backend.commercial.customer_setup_bootstrap_coordinator as coordinator_module

from backend.commercial.customer_setup_bootstrap_coordinator import (
    CustomerSetupBootstrapCoordinator,
)
from backend.commercial.customer_setup_bootstrap_http_client import (
    CustomerSetupBootstrapTransportResult,
)
from backend.commercial.customer_setup_bootstrap_input import (
    CustomerSetupBootstrapInput,
)


BASE_URL = "https://api.todobagroup.com"

AUTHORIZATION_CODE = (
    "tdbba."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)

CODE_VERIFIER = (
    "V" * 64
)

LAUNCH_CREDENTIAL = (
    "tdbsl."
    + ("2" * 32)
    + "."
    + ("B" * 43)
)

EXPIRES_AT = (
    "2026-08-31T13:30:00.000000Z"
)


class _MT5Module:
    pass


def _coordinator(
    *,
    tmp_path,
    setup_base_url=BASE_URL,
    authorization_code=AUTHORIZATION_CODE,
    code_verifier=CODE_VERIFIER,
    mt5_module=_MT5Module,
):
    return CustomerSetupBootstrapCoordinator(
        setup_base_url=(
            setup_base_url
        ),
        authorization_code=(
            authorization_code
        ),
        code_verifier=(
            code_verifier
        ),
        mt5_module=mt5_module,
        roaming_appdata_path=tmp_path,
    )


def _transport_result(
) -> CustomerSetupBootstrapTransportResult:
    return CustomerSetupBootstrapTransportResult(
        setup_launch_credential=(
            LAUNCH_CREDENTIAL
        ),
        expires_at=EXPIRES_AT,
    )


def test_run_composes_exact_bootstrap_to_launcher_order(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            calls.append(
                (
                    "bootstrap_client",
                    kwargs,
                )
            )

        def exchange(
            self,
        ):
            calls.append(
                (
                    "bootstrap_exchange",
                    {},
                )
            )

            return _transport_result()

    class FakeBootstrapInput:
        def __init__(
            self,
            **kwargs,
        ):
            calls.append(
                (
                    "bootstrap_input",
                    kwargs,
                )
            )

    class FakeLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            calls.append(
                (
                    "launcher",
                    kwargs,
                )
            )

        def run(
            self,
        ):
            calls.append(
                (
                    "launcher_run",
                    {},
                )
            )

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapInput",
        FakeBootstrapInput,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        FakeLauncher,
    )

    coordinator = _coordinator(
        tmp_path=tmp_path
    )

    result = coordinator.run()

    assert result is None

    assert calls[0] == (
        "bootstrap_client",
        {
            "setup_base_url": BASE_URL,
            "authorization_code": (
                AUTHORIZATION_CODE
            ),
            "code_verifier": (
                CODE_VERIFIER
            ),
        },
    )

    assert calls[1] == (
        "bootstrap_exchange",
        {},
    )

    assert calls[2][0] == (
        "bootstrap_input"
    )

    assert calls[2][1][
        "setup_base_url"
    ] == BASE_URL

    assert calls[2][1][
        "setup_launch_credential"
    ] == LAUNCH_CREDENTIAL

    assert calls[3][0] == "launcher"

    assert calls[3][1][
        "mt5_module"
    ] is _MT5Module

    assert calls[3][1][
        "roaming_appdata_path"
    ] == tmp_path

    assert calls[3][1][
        "bootstrap_input"
    ] is not None

    assert calls[4] == (
        "launcher_run",
        {},
    )


def test_bootstrap_exchange_happens_before_bootstrap_input(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def exchange(
            self,
        ):
            calls.append(
                "exchange"
            )
            return _transport_result()

    class StopBootstrapInput:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

            calls.append(
                "bootstrap_input"
            )

            raise RuntimeError(
                "stop after bootstrap input evidence"
            )

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapInput",
        StopBootstrapInput,
    )

    with pytest.raises(
        RuntimeError,
        match="bootstrap input evidence",
    ):
        _coordinator(
            tmp_path=tmp_path
        ).run()

    assert calls == [
        "exchange",
        "bootstrap_input",
    ]


def test_bootstrap_failure_prevents_all_downstream_composition(
    monkeypatch,
    tmp_path,
) -> None:
    downstream_calls = []

    class FailingBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def exchange(
            self,
        ):
            raise RuntimeError(
                "bootstrap exchange failed"
            )

    class ForbiddenDownstream:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            downstream_calls.append(
                (
                    args,
                    kwargs,
                )
            )

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FailingBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapInput",
        ForbiddenDownstream,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        ForbiddenDownstream,
    )

    with pytest.raises(
        RuntimeError,
        match="bootstrap exchange failed",
    ):
        _coordinator(
            tmp_path=tmp_path
        ).run()

    assert downstream_calls == []


def test_invalid_bootstrap_result_prevents_downstream_composition(
    monkeypatch,
    tmp_path,
) -> None:
    downstream_calls = []

    class InvalidBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def exchange(
            self,
        ):
            return object()

    class ForbiddenDownstream:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            downstream_calls.append(
                (
                    args,
                    kwargs,
                )
            )

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        InvalidBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapInput",
        ForbiddenDownstream,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        ForbiddenDownstream,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "bootstrap exchange returned "
            "invalid result"
        ),
    ):
        _coordinator(
            tmp_path=tmp_path
        ).run()

    assert downstream_calls == []


def test_launch_credential_flows_only_from_bootstrap_result(
    monkeypatch,
    tmp_path,
) -> None:
    observed = {}

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def exchange(
            self,
        ):
            return _transport_result()

    class CapturingLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            observed.update(
                kwargs
            )

        def run(
            self,
        ):
            return None

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        CapturingLauncher,
    )

    _coordinator(
        tmp_path=tmp_path
    ).run()

    bootstrap_input = observed[
        "bootstrap_input"
    ]

    assert isinstance(
        bootstrap_input,
        CustomerSetupBootstrapInput,
    )

    assert (
        bootstrap_input.setup_launch_credential
        == LAUNCH_CREDENTIAL
    )


def test_same_base_url_flows_to_exchange_and_launcher_input(
    monkeypatch,
    tmp_path,
) -> None:
    observed = {}

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "bootstrap_client"
            ] = kwargs

        def exchange(
            self,
        ):
            return _transport_result()

    class CapturingLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "launcher"
            ] = kwargs

        def run(
            self,
        ):
            return None

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        CapturingLauncher,
    )

    _coordinator(
        tmp_path=tmp_path
    ).run()

    assert observed[
        "bootstrap_client"
    ][
        "setup_base_url"
    ] == BASE_URL

    assert (
        observed[
            "launcher"
        ][
            "bootstrap_input"
        ].setup_base_url
        == BASE_URL
    )


def test_pkce_material_is_passed_only_to_bootstrap_transport(
    monkeypatch,
    tmp_path,
) -> None:
    observed = {}

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "bootstrap"
            ] = kwargs

        def exchange(
            self,
        ):
            return _transport_result()

    class FakeBootstrapInput:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "input"
            ] = kwargs

    class FakeLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "launcher"
            ] = kwargs

        def run(
            self,
        ):
            return None

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapInput",
        FakeBootstrapInput,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        FakeLauncher,
    )

    _coordinator(
        tmp_path=tmp_path
    ).run()

    assert observed[
        "bootstrap"
    ][
        "authorization_code"
    ] == AUTHORIZATION_CODE

    assert observed[
        "bootstrap"
    ][
        "code_verifier"
    ] == CODE_VERIFIER

    assert (
        "authorization_code"
        not in observed["input"]
    )
    assert (
        "code_verifier"
        not in observed["input"]
    )

    assert (
        "authorization_code"
        not in observed["launcher"]
    )
    assert (
        "code_verifier"
        not in observed["launcher"]
    )


def test_mt5_module_and_roaming_path_flow_only_to_launcher(
    monkeypatch,
    tmp_path,
) -> None:
    observed = {}

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "bootstrap"
            ] = kwargs

        def exchange(
            self,
        ):
            return _transport_result()

    class FakeBootstrapInput:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "input"
            ] = kwargs

    class FakeLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "launcher"
            ] = kwargs

        def run(
            self,
        ):
            return None

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapInput",
        FakeBootstrapInput,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        FakeLauncher,
    )

    _coordinator(
        tmp_path=tmp_path
    ).run()

    assert (
        "mt5_module"
        not in observed["bootstrap"]
    )
    assert (
        "roaming_appdata_path"
        not in observed["bootstrap"]
    )

    assert (
        "mt5_module"
        not in observed["input"]
    )
    assert (
        "roaming_appdata_path"
        not in observed["input"]
    )

    assert observed[
        "launcher"
    ][
        "mt5_module"
    ] is _MT5Module

    assert observed[
        "launcher"
    ][
        "roaming_appdata_path"
    ] == tmp_path


def test_bootstrap_client_is_constructed_once(
    monkeypatch,
    tmp_path,
) -> None:
    count = 0

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            nonlocal count
            del kwargs

            count += 1

        def exchange(
            self,
        ):
            return _transport_result()

    class FakeLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def run(
            self,
        ):
            return None

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        FakeLauncher,
    )

    _coordinator(
        tmp_path=tmp_path
    ).run()

    assert count == 1


def test_bootstrap_exchange_is_called_once(
    monkeypatch,
    tmp_path,
) -> None:
    count = 0

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def exchange(
            self,
        ):
            nonlocal count

            count += 1
            return _transport_result()

    class FakeLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def run(
            self,
        ):
            return None

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        FakeLauncher,
    )

    _coordinator(
        tmp_path=tmp_path
    ).run()

    assert count == 1


def test_launcher_is_constructed_once(
    monkeypatch,
    tmp_path,
) -> None:
    count = 0

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def exchange(
            self,
        ):
            return _transport_result()

    class FakeLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            nonlocal count
            del kwargs

            count += 1

        def run(
            self,
        ):
            return None

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        FakeLauncher,
    )

    _coordinator(
        tmp_path=tmp_path
    ).run()

    assert count == 1


def test_launcher_run_is_called_once(
    monkeypatch,
    tmp_path,
) -> None:
    count = 0

    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def exchange(
            self,
        ):
            return _transport_result()

    class FakeLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def run(
            self,
        ):
            nonlocal count

            count += 1

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        FakeLauncher,
    )

    _coordinator(
        tmp_path=tmp_path
    ).run()

    assert count == 1


def test_launcher_failure_propagates(
    monkeypatch,
    tmp_path,
) -> None:
    class FakeBootstrapClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def exchange(
            self,
        ):
            return _transport_result()

    class FailingLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def run(
            self,
        ):
            raise RuntimeError(
                "launcher failed"
            )

    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupBootstrapHttpClient",
        FakeBootstrapClient,
    )
    monkeypatch.setattr(
        coordinator_module,
        "CustomerSetupLauncher",
        FailingLauncher,
    )

    with pytest.raises(
        RuntimeError,
        match="launcher failed",
    ):
        _coordinator(
            tmp_path=tmp_path
        ).run()


def test_coordinator_repr_redacts_bootstrap_secrets(
    tmp_path,
) -> None:
    coordinator = _coordinator(
        tmp_path=tmp_path
    )

    rendered = repr(
        coordinator
    )

    assert (
        AUTHORIZATION_CODE
        not in rendered
    )

    assert (
        CODE_VERIFIER
        not in rendered
    )

    assert (
        "authorization_code=<redacted>"
        in rendered
    )

    assert (
        "code_verifier=<redacted>"
        in rendered
    )

    assert BASE_URL in rendered


def test_coordinator_uses_slots(
    tmp_path,
) -> None:
    coordinator = _coordinator(
        tmp_path=tmp_path
    )

    assert not hasattr(
        coordinator,
        "__dict__",
    )


def test_constructor_surface_is_exact_bootstrap_composition(
) -> None:
    parameters = set(
        inspect.signature(
            CustomerSetupBootstrapCoordinator.__init__
        ).parameters
    )

    assert parameters == {
        "self",
        "setup_base_url",
        "authorization_code",
        "code_verifier",
        "mt5_module",
        "roaming_appdata_path",
    }


def test_run_signature_accepts_no_new_input(
) -> None:
    parameters = set(
        inspect.signature(
            CustomerSetupBootstrapCoordinator.run
        ).parameters
    )

    assert parameters == {
        "self",
    }


def test_owner_imports_only_required_customer_setup_owners(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_coordinator.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_modules = {
        node.module
        for node in ast.walk(
            tree
        )
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
        )
    }

    actual_commercial_imports = {
        module
        for module in imported_modules
        if module.startswith(
            "backend.commercial."
        )
    }

    assert actual_commercial_imports == {
        (
            "backend.commercial."
            "customer_setup_bootstrap_http_client"
        ),
        (
            "backend.commercial."
            "customer_setup_bootstrap_input"
        ),
        (
            "backend.commercial."
            "customer_setup_launcher"
        ),
    }


def test_owner_has_no_bootstrap_acquisition_authority(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_coordinator.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    forbidden_import_roots = {
        "argparse",
        "httpx",
        "json",
        "os",
        "requests",
        "secrets",
        "sys",
        "tkinter",
    }

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

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imported_roots.add(
                    node.module.split(
                        ".",
                        1,
                    )[0]
                )

    assert forbidden_import_roots.isdisjoint(
        imported_roots
    )

    forbidden_owner_names = {
        "CustomerSetupBootstrapAuthorizationService",
        "CustomerSetupBootstrapAuthorizationStore",
        "CustomerSetupBootstrapLaunchGrantService",
        "CustomerSetupLaunchCredentialService",
        "CustomerSetupLaunchCredentialStore",
    }

    imported_names = {
        alias.name
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            ast.ImportFrom,
        )
        for alias in node.names
    }

    assert forbidden_owner_names.isdisjoint(
        imported_names
    )


def test_owner_does_not_generate_pkce_material(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_coordinator.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    called_names = set()

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        rendered = (
            ast.get_source_segment(
                source,
                node.func,
            )
            or ""
        )

        called_names.add(
            rendered
        )

    forbidden_calls = {
        "secrets.token_urlsafe",
        "secrets.token_hex",
        "derive_pkce_s256_code_challenge",
    }

    assert forbidden_calls.isdisjoint(
        called_names
    )


def test_owner_exposes_no_business_identity_input(
) -> None:
    parameters = set(
        inspect.signature(
            CustomerSetupBootstrapCoordinator.__init__
        ).parameters
    )

    forbidden = {
        "customer_id",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
        "registration_request_id",
        "activation_request_id",
        "setup_activation_id",
        "payment_id",
        "subscription_id",
        "handoff_credential",
        "setup_launch_credential",
    }

    assert forbidden.isdisjoint(
        parameters
    )


def test_owner_has_no_runtime_or_trading_imports(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_coordinator.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_modules = {
        node.module
        for node in ast.walk(
            tree
        )
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
        )
    }

    assert all(
        not module.startswith(
            "backend.runtime"
        )
        for module in imported_modules
    )

    assert all(
        not module.startswith(
            "backend.trading"
        )
        for module in imported_modules
    )


def test_owner_does_not_import_entry_transport_directly(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_coordinator.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "customer_setup_entry_http_client"
        not in source
    )

    assert (
        "CustomerSetupEntryHttpClient"
        not in source
    )


def test_owner_does_not_read_environment_or_config(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_coordinator.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    forbidden = (
        "os.environ",
        "getenv(",
        "backend.config",
        "TODOBA_CLOUD_BASE_URL",
        "initialize_empty(",
        "open_existing(",
    )

    for token in forbidden:
        assert token not in source


def test_coordinator_defines_only_init_repr_and_run_methods(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_coordinator.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    classes = [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.ClassDef,
            )
            and node.name
            == "CustomerSetupBootstrapCoordinator"
        )
    ]

    assert len(
        classes
    ) == 1

    method_names = {
        node.name
        for node in classes[
            0
        ].body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    }

    assert method_names == {
        "__init__",
        "__repr__",
        "run",
    }


def test_bootstrap_result_type_is_explicitly_enforced(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_bootstrap_coordinator.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "CustomerSetupBootstrapTransportResult"
        in source
    )

    assert "isinstance(" in source


def test_coordinator_does_not_mutate_existing_launcher_contract(
) -> None:
    launcher_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_launcher.py"
    )

    source = launcher_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    launcher_classes = [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.ClassDef,
            )
            and node.name
            == "CustomerSetupLauncher"
        )
    ]

    assert len(
        launcher_classes
    ) == 1

    methods = {
        node.name
        for node in launcher_classes[0].body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    }

    assert methods == {
        "__init__",
        "__repr__",
        "run",
    }
