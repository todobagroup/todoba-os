"""
Owner tests for TODOBA Customer Setup Launcher.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import backend.commercial.customer_setup_launcher as launcher_module

from backend.commercial.customer_setup_bootstrap_input import (
    CustomerSetupBootstrapInput,
)
from backend.commercial.customer_setup_launcher import (
    CustomerSetupLauncher,
)


BASE_URL = "https://api.todobagroup.com"

LAUNCH_CREDENTIAL = (
    "tdbsl."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)

HANDOFF_CREDENTIAL = (
    "tdbsh."
    + ("2" * 32)
    + "."
    + ("B" * 43)
)


class _MT5Module:
    ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 2

    @staticmethod
    def initialize():
        return True

    @staticmethod
    def shutdown():
        return None

    @staticmethod
    def terminal_info():
        return None

    @staticmethod
    def account_info():
        return None


def _bootstrap(
) -> CustomerSetupBootstrapInput:
    return CustomerSetupBootstrapInput(
        setup_base_url=BASE_URL,
        setup_launch_credential=(
            LAUNCH_CREDENTIAL
        ),
    )


def test_launcher_validates_local_inputs_before_entry_exchange(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    class FakePreflight:
        def __init__(
            self,
            *,
            mt5_module,
        ):
            calls.append(
                (
                    "preflight",
                    mt5_module,
                )
            )

    class ForbiddenEntryClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs
            raise AssertionError(
                "Entry exchange must not happen "
                "during launcher construction."
            )

    monkeypatch.setattr(
        launcher_module,
        "CustomerMT5SetupPreflightService",
        FakePreflight,
    )

    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupEntryHttpClient",
        ForbiddenEntryClient,
    )

    launcher = CustomerSetupLauncher(
        bootstrap_input=_bootstrap(),
        mt5_module=_MT5Module,
        roaming_appdata_path=tmp_path,
    )

    assert isinstance(
        launcher,
        CustomerSetupLauncher,
    )

    assert calls == [
        (
            "preflight",
            _MT5Module,
        )
    ]


def test_invalid_bootstrap_is_rejected_before_mt5_validation(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    class FakePreflight:
        def __init__(
            self,
            **kwargs,
        ):
            calls.append(
                kwargs
            )

    monkeypatch.setattr(
        launcher_module,
        "CustomerMT5SetupPreflightService",
        FakePreflight,
    )

    with pytest.raises(
        TypeError,
        match=(
            "bootstrap_input must be "
            "CustomerSetupBootstrapInput"
        ),
    ):
        CustomerSetupLauncher(
            bootstrap_input=object(),
            mt5_module=_MT5Module,
            roaming_appdata_path=tmp_path,
        )

    assert calls == []


def test_invalid_roaming_appdata_is_rejected_before_mt5_validation(
    monkeypatch,
) -> None:
    calls = []

    class FakePreflight:
        def __init__(
            self,
            **kwargs,
        ):
            calls.append(
                kwargs
            )

    monkeypatch.setattr(
        launcher_module,
        "CustomerMT5SetupPreflightService",
        FakePreflight,
    )

    with pytest.raises(
        TypeError,
        match=(
            "roaming_appdata_path must be Path"
        ),
    ):
        CustomerSetupLauncher(
            bootstrap_input=_bootstrap(),
            mt5_module=_MT5Module,
            roaming_appdata_path="bad",
        )

    assert calls == []


def test_real_mt5_preflight_validation_is_preserved(
    tmp_path,
) -> None:
    with pytest.raises(
        TypeError,
    ):
        CustomerSetupLauncher(
            bootstrap_input=_bootstrap(),
            mt5_module=object(),
            roaming_appdata_path=tmp_path,
        )


def test_run_composes_exact_customer_setup_chain(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    preflight_instance = object()
    entry_client_instance = object()
    setup_http_client_instance = object()
    installer_instance = object()
    orchestration_instance = object()
    controller_instance = object()
    gui_instance = object()

    class EntryResult:
        handoff_credential = (
            HANDOFF_CREDENTIAL
        )

    class FakePreflight:
        def __new__(
            cls,
            *,
            mt5_module,
        ):
            calls.append(
                (
                    "preflight",
                    {
                        "mt5_module": (
                            mt5_module
                        )
                    },
                )
            )
            return preflight_instance

    class FakeEntryClient:
        def __new__(
            cls,
            *,
            setup_base_url,
            setup_launch_credential,
        ):
            calls.append(
                (
                    "entry_client",
                    {
                        "setup_base_url": (
                            setup_base_url
                        ),
                        "setup_launch_credential": (
                            setup_launch_credential
                        ),
                    },
                )
            )
            return entry_client_instance

    class FakeSetupHttpClient:
        def __new__(
            cls,
            *,
            setup_base_url,
            setup_handoff_credential,
        ):
            calls.append(
                (
                    "setup_http_client",
                    {
                        "setup_base_url": (
                            setup_base_url
                        ),
                        "setup_handoff_credential": (
                            setup_handoff_credential
                        ),
                    },
                )
            )
            return setup_http_client_instance

    class FakeInstaller:
        def __new__(
            cls,
        ):
            calls.append(
                (
                    "installer",
                    {},
                )
            )
            return installer_instance

    class FakeOrchestration:
        def __new__(
            cls,
            *,
            setup_http_client,
            ex5_installer_service,
        ):
            calls.append(
                (
                    "orchestration",
                    {
                        "setup_http_client": (
                            setup_http_client
                        ),
                        "ex5_installer_service": (
                            ex5_installer_service
                        ),
                    },
                )
            )
            return orchestration_instance

    class FakeController:
        def __new__(
            cls,
            *,
            mt5_preflight_service,
            setup_orchestration_service,
        ):
            calls.append(
                (
                    "controller",
                    {
                        "mt5_preflight_service": (
                            mt5_preflight_service
                        ),
                        "setup_orchestration_service": (
                            setup_orchestration_service
                        ),
                    },
                )
            )
            return controller_instance

    class FakeGui:
        def __new__(
            cls,
            *,
            controller,
            roaming_appdata_path,
        ):
            calls.append(
                (
                    "gui",
                    {
                        "controller": (
                            controller
                        ),
                        "roaming_appdata_path": (
                            roaming_appdata_path
                        ),
                    },
                )
            )
            return gui_instance

    def fake_exchange():
        calls.append(
            (
                "entry_exchange",
                {},
            )
        )
        return EntryResult()

    def fake_gui_run():
        calls.append(
            (
                "gui_run",
                {},
            )
        )

    monkeypatch.setattr(
        launcher_module,
        "CustomerMT5SetupPreflightService",
        FakePreflight,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupEntryHttpClient",
        FakeEntryClient,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupHttpClient",
        FakeSetupHttpClient,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerMT5EX5InstallerService",
        FakeInstaller,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupOrchestrationService",
        FakeOrchestration,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupApplicationController",
        FakeController,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupGuiShell",
        FakeGui,
    )

    # object() cannot receive instance methods through its
    # concrete class without affecting all objects. Replace
    # the two transport endpoint instances with small shells.
    class EntryShell:
        def exchange(
            self,
        ):
            return fake_exchange()

    class GuiShell:
        def run(
            self,
        ):
            fake_gui_run()

    entry_shell = EntryShell()
    gui_shell = GuiShell()

    class FakeEntryClientFinal:
        def __new__(
            cls,
            *,
            setup_base_url,
            setup_launch_credential,
        ):
            calls.append(
                (
                    "entry_client",
                    {
                        "setup_base_url": (
                            setup_base_url
                        ),
                        "setup_launch_credential": (
                            setup_launch_credential
                        ),
                    },
                )
            )
            return entry_shell

    class FakeGuiFinal:
        def __new__(
            cls,
            *,
            controller,
            roaming_appdata_path,
        ):
            calls.append(
                (
                    "gui",
                    {
                        "controller": (
                            controller
                        ),
                        "roaming_appdata_path": (
                            roaming_appdata_path
                        ),
                    },
                )
            )
            return gui_shell

    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupEntryHttpClient",
        FakeEntryClientFinal,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupGuiShell",
        FakeGuiFinal,
    )

    launcher = CustomerSetupLauncher(
        bootstrap_input=_bootstrap(),
        mt5_module=_MT5Module,
        roaming_appdata_path=tmp_path,
    )

    result = launcher.run()

    assert result is None

    assert calls == [
        (
            "preflight",
            {
                "mt5_module": _MT5Module,
            },
        ),
        (
            "entry_client",
            {
                "setup_base_url": BASE_URL,
                "setup_launch_credential": (
                    LAUNCH_CREDENTIAL
                ),
            },
        ),
        (
            "entry_exchange",
            {},
        ),
        (
            "setup_http_client",
            {
                "setup_base_url": BASE_URL,
                "setup_handoff_credential": (
                    HANDOFF_CREDENTIAL
                ),
            },
        ),
        (
            "installer",
            {},
        ),
        (
            "orchestration",
            {
                "setup_http_client": (
                    setup_http_client_instance
                ),
                "ex5_installer_service": (
                    installer_instance
                ),
            },
        ),
        (
            "controller",
            {
                "mt5_preflight_service": (
                    preflight_instance
                ),
                "setup_orchestration_service": (
                    orchestration_instance
                ),
            },
        ),
        (
            "gui",
            {
                "controller": (
                    controller_instance
                ),
                "roaming_appdata_path": (
                    tmp_path
                ),
            },
        ),
        (
            "gui_run",
            {},
        ),
    ]


def test_entry_exchange_happens_before_handoff_transport(
    monkeypatch,
    tmp_path,
) -> None:
    calls = []

    class FakePreflight:
        def __init__(
            self,
            *,
            mt5_module,
        ):
            del mt5_module

    class EntryResult:
        handoff_credential = (
            HANDOFF_CREDENTIAL
        )

    class FakeEntryClient:
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
            return EntryResult()

    class StopSetupHttpClient:
        def __init__(
            self,
            **kwargs,
        ):
            calls.append(
                "handoff_transport"
            )
            raise RuntimeError(
                "stop after ordering evidence"
            )

    monkeypatch.setattr(
        launcher_module,
        "CustomerMT5SetupPreflightService",
        FakePreflight,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupEntryHttpClient",
        FakeEntryClient,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupHttpClient",
        StopSetupHttpClient,
    )

    launcher = CustomerSetupLauncher(
        bootstrap_input=_bootstrap(),
        mt5_module=_MT5Module,
        roaming_appdata_path=tmp_path,
    )

    with pytest.raises(
        RuntimeError,
        match="ordering evidence",
    ):
        launcher.run()

    assert calls == [
        "exchange",
        "handoff_transport",
    ]


def test_entry_failure_prevents_downstream_composition(
    monkeypatch,
    tmp_path,
) -> None:
    downstream_calls = []

    class FakePreflight:
        def __init__(
            self,
            *,
            mt5_module,
        ):
            del mt5_module

    class FailingEntryClient:
        def __init__(
            self,
            **kwargs,
        ):
            del kwargs

        def exchange(
            self,
        ):
            raise RuntimeError(
                "entry failed"
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
        launcher_module,
        "CustomerMT5SetupPreflightService",
        FakePreflight,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupEntryHttpClient",
        FailingEntryClient,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupHttpClient",
        ForbiddenDownstream,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerMT5EX5InstallerService",
        ForbiddenDownstream,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupOrchestrationService",
        ForbiddenDownstream,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupApplicationController",
        ForbiddenDownstream,
    )
    monkeypatch.setattr(
        launcher_module,
        "CustomerSetupGuiShell",
        ForbiddenDownstream,
    )

    launcher = CustomerSetupLauncher(
        bootstrap_input=_bootstrap(),
        mt5_module=_MT5Module,
        roaming_appdata_path=tmp_path,
    )

    with pytest.raises(
        RuntimeError,
        match="entry failed",
    ):
        launcher.run()

    assert downstream_calls == []


def test_launcher_repr_redacts_launch_credential(
    tmp_path,
) -> None:
    launcher = CustomerSetupLauncher(
        bootstrap_input=_bootstrap(),
        mt5_module=_MT5Module,
        roaming_appdata_path=tmp_path,
    )

    rendered = repr(
        launcher
    )

    assert (
        LAUNCH_CREDENTIAL
        not in rendered
    )
    assert (
        "setup_launch_credential=<redacted>"
        in rendered
    )
    assert (
        BASE_URL
        in rendered
    )


def test_launcher_uses_slots(
    tmp_path,
) -> None:
    launcher = CustomerSetupLauncher(
        bootstrap_input=_bootstrap(),
        mt5_module=_MT5Module,
        roaming_appdata_path=tmp_path,
    )

    assert not hasattr(
        launcher,
        "__dict__",
    )


def test_launcher_imports_only_existing_customer_setup_owners(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_launcher.py"
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

    expected_commercial_imports = {
        (
            "backend.commercial."
            "customer_mt5_ex5_installer_service"
        ),
        (
            "backend.commercial."
            "customer_mt5_setup_preflight_service"
        ),
        (
            "backend.commercial."
            "customer_setup_application_controller"
        ),
        (
            "backend.commercial."
            "customer_setup_bootstrap_input"
        ),
        (
            "backend.commercial."
            "customer_setup_entry_http_client"
        ),
        (
            "backend.commercial."
            "customer_setup_gui_shell"
        ),
        (
            "backend.commercial."
            "customer_setup_http_client"
        ),
        (
            "backend.commercial."
            "customer_setup_orchestration_service"
        ),
    }

    actual_commercial_imports = {
        module
        for module in imported_modules
        if module.startswith(
            "backend.commercial."
        )
    }

    assert (
        actual_commercial_imports
        == expected_commercial_imports
    )


def test_launcher_has_no_bootstrap_acquisition_authority(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_launcher.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    forbidden_import_roots = {
        "argparse",
        "os",
        "sys",
        "json",
        "httpx",
        "requests",
        "tkinter",
        "MetaTrader5",
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


def test_launcher_exposes_no_business_identity_input(
) -> None:
    init = (
        CustomerSetupLauncher.__init__
    )

    parameters = set(
        __import__(
            "inspect"
        ).signature(
            init
        ).parameters
    )

    assert parameters == {
        "self",
        "bootstrap_input",
        "mt5_module",
        "roaming_appdata_path",
    }

    forbidden = {
        "customer_id",
        "deployment_id",
        "agent_id",
        "account_fingerprint",
        "registration_request_id",
        "grant_request_id",
        "handoff_credential",
    }

    assert forbidden.isdisjoint(
        parameters
    )


def test_launcher_has_no_runtime_or_trading_readiness_owner(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_launcher.py"
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


def test_launcher_defines_only_init_repr_and_run_methods(
) -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_launcher.py"
    )

    source = source_path.read_text(
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

    method_names = {
        node.name
        for node in launcher_classes[
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