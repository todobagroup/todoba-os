"""
Owner tests for production TODOBA Setup entrypoint.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.customer_setup as customer_setup_module


AUTHORIZATION_CODE = (
    "tdbba."
    + ("1" * 32)
    + "."
    + ("A" * 43)
)


ACTIVATION_CODE = (
    "tdbsa."
    + ("2" * 32)
    + "."
    + ("B" * 43)
)


SETUP_CHALLENGE = (
    "B" * 43
)

APPDATA_PATH = (
    r"C:\Users\Customer\AppData\Roaming"
)


class FakeVariable:
    def __init__(
        self,
        value="",
    ):
        self.value = value
        self.set_values = []

    def get(
        self,
    ):
        return self.value

    def set(
        self,
        value,
    ):
        self.value = value
        self.set_values.append(
            value
        )


class FakeButton:
    def __init__(
        self,
    ):
        self.states = []

    def configure(
        self,
        **kwargs,
    ):
        self.states.append(
            kwargs
        )


class FakeRoot:
    def __init__(
        self,
    ):
        self.calls = []
        self.clipboard_value = None

    def withdraw(
        self,
    ):
        self.calls.append(
            "withdraw"
        )

    def deiconify(
        self,
    ):
        self.calls.append(
            "deiconify"
        )

    def update_idletasks(
        self,
    ):
        self.calls.append(
            "update_idletasks"
        )

    def destroy(
        self,
    ):
        self.calls.append(
            "destroy"
        )

    def clipboard_clear(
        self,
    ):
        self.calls.append(
            "clipboard_clear"
        )

    def clipboard_append(
        self,
        value,
    ):
        self.calls.append(
            "clipboard_append"
        )
        self.clipboard_value = value

    def update(
        self,
    ):
        self.calls.append(
            "update"
        )


class FakeAcquisition:
    def __init__(
        self,
        *,
        challenge=SETUP_CHALLENGE,
        failure=None,
    ):
        self.code_challenge_s256 = (
            challenge
        )
        self.failure = failure
        self.launch_calls = []

    def launch(
        self,
        *,
        authorization_code,
    ):
        self.launch_calls.append(
            authorization_code
        )

        if self.failure is not None:
            raise self.failure


class FakeBridge:
    def __init__(
        self,
        *,
        failure=None,
    ):
        self.launch_calls = []
        self.failure = failure

    def launch(
        self,
        *,
        activation_code,
    ):
        self.launch_calls.append(
            activation_code
        )

        if self.failure is not None:
            raise self.failure



def _window_for_submission(
    monkeypatch,
    *,
    activation_code=ACTIVATION_CODE,
    bridge=None,
):
    if bridge is None:
        bridge = FakeBridge()

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupAccessCodeBootstrapBridge",
        FakeBridge,
    )

    window = (
        customer_setup_module
        .CustomerSetupBootstrapWindow(
            bridge=bridge,
        )
    )

    root = FakeRoot()

    activation_var = (
        FakeVariable(
            activation_code
        )
    )

    status_var = (
        FakeVariable()
    )

    button = (
        FakeButton()
    )

    window._root = root
    window._activation_code_var = (
        activation_var
    )
    window._status_var = (
        status_var
    )
    window._start_button = button

    return (
        window,
        bridge,
        root,
        activation_var,
        status_var,
        button,
    )



def test_locked_customer_window_identity(
) -> None:
    assert (
        customer_setup_module.WINDOW_TITLE
        == "TODOBA Trading AI Setup"
    )

    assert (
        customer_setup_module.WELCOME_HEADLINE
        == "Welcome to TODOBA Trading"
    )


def test_production_flow_uses_authoritative_cloud_base_url(
    monkeypatch,
) -> None:
    observed = {}

    class FakeProductionAcquisition:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "acquisition"
            ] = kwargs

            observed[
                "acquisition_instance"
            ] = self

    class FakeAccessCodeClient:
        def __init__(
            self,
            **kwargs,
        ):
            observed[
                "access_code_client"
            ] = kwargs

            observed[
                "access_code_client_instance"
            ] = self

    class FakeProductionBridge:
        def __init__(
            self,
            *,
            access_code_client,
            acquisition,
        ):
            observed[
                "bridge_access_code_client"
            ] = access_code_client

            observed[
                "bridge_acquisition"
            ] = acquisition

            observed[
                "bridge_instance"
            ] = self

    class FakeWindow:
        def __init__(
            self,
            *,
            bridge,
        ):
            observed[
                "window_bridge"
            ] = bridge

        def run(
            self,
        ):
            observed[
                "run"
            ] = (
                observed.get(
                    "run",
                    0,
                )
                + 1
            )

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupBootstrapAcquisition",
        FakeProductionAcquisition,
    )

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupAccessCodeHttpClient",
        FakeAccessCodeClient,
    )

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupAccessCodeBootstrapBridge",
        FakeProductionBridge,
    )

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupBootstrapWindow",
        FakeWindow,
    )

    monkeypatch.setattr(
        customer_setup_module,
        "_resolve_roaming_appdata_path",
        lambda: Path(APPDATA_PATH),
    )

    fake_mt5 = object()

    monkeypatch.setattr(
        customer_setup_module,
        "mt5",
        fake_mt5,
    )

    customer_setup_module.run_production_customer_setup()

    assert observed[
        "acquisition"
    ][
        "setup_base_url"
    ] == customer_setup_module.TODOBA_CLOUD_BASE_URL

    assert observed[
        "acquisition"
    ][
        "mt5_module"
    ] is fake_mt5

    assert observed[
        "acquisition"
    ][
        "roaming_appdata_path"
    ] == Path(
        APPDATA_PATH
    )

    assert observed[
        "access_code_client"
    ] == {
        "setup_base_url": (
            customer_setup_module
            .TODOBA_CLOUD_BASE_URL
        ),
    }

    assert observed[
        "bridge_access_code_client"
    ] is observed[
        "access_code_client_instance"
    ]

    assert observed[
        "bridge_acquisition"
    ] is observed[
        "acquisition_instance"
    ]

    assert observed[
        "window_bridge"
    ] is observed[
        "bridge_instance"
    ]

    assert observed[
        "run"
    ] == 1



def test_windows_appdata_is_authoritative_roaming_path(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "APPDATA",
        APPDATA_PATH,
    )

    assert (
        customer_setup_module
        ._resolve_roaming_appdata_path()
        == Path(APPDATA_PATH)
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
    ],
)
def test_missing_windows_appdata_fails_closed(
    monkeypatch,
    value,
) -> None:
    if value is None:
        monkeypatch.delenv(
            "APPDATA",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "APPDATA",
            value,
        )

    with pytest.raises(
        RuntimeError,
        match="Windows APPDATA is not available",
    ):
        customer_setup_module._resolve_roaming_appdata_path()


def test_bootstrap_window_requires_bridge_owner(
    monkeypatch,
) -> None:
    class RequiredBridge:
        pass

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupAccessCodeBootstrapBridge",
        RequiredBridge,
    )

    with pytest.raises(
        TypeError,
        match=(
            "bridge must be "
            "CustomerSetupAccessCodeBootstrapBridge"
        ),
    ):
        customer_setup_module.CustomerSetupBootstrapWindow(
            bridge=object(),
        )



def test_empty_activation_code_never_crosses_boundary(
    monkeypatch,
) -> None:
    (
        window,
        bridge,
        root,
        activation_var,
        status_var,
        button,
    ) = _window_for_submission(
        monkeypatch,
        activation_code="   ",
    )

    window._submit_activation_code()

    assert bridge.launch_calls == []

    assert (
        activation_var.value
        == "   "
    )

    assert (
        "Activation Code"
        in status_var.value
    )

    assert (
        "withdraw"
        not in root.calls
    )

    assert (
        "disabled"
        not in button.states
    )



def test_activation_code_is_stripped_before_launch(
    monkeypatch,
) -> None:
    (
        window,
        bridge,
        _root,
        _activation_var,
        _status_var,
        _button,
    ) = _window_for_submission(
        monkeypatch,
        activation_code=(
            f"  {ACTIVATION_CODE}  "
        ),
    )

    window._submit_activation_code()

    assert bridge.launch_calls == [
        ACTIVATION_CODE,
    ]



def test_plaintext_activation_widget_is_cleared_before_launch(
    monkeypatch,
) -> None:
    observed = {}

    activation_var = (
        FakeVariable(
            ACTIVATION_CODE
        )
    )

    class InspectingBridge(
        FakeBridge
    ):
        def launch(
            self,
            *,
            activation_code,
        ):
            observed[
                "activation_widget_value_at_launch"
            ] = activation_var.value

            super().launch(
                activation_code=(
                    activation_code
                )
            )

    bridge = InspectingBridge()

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupAccessCodeBootstrapBridge",
        InspectingBridge,
    )

    window = (
        customer_setup_module
        .CustomerSetupBootstrapWindow(
            bridge=bridge,
        )
    )

    root = FakeRoot()
    status_var = FakeVariable()
    button = FakeButton()

    window._root = root
    window._activation_code_var = (
        activation_var
    )
    window._status_var = status_var
    window._start_button = button

    window._submit_activation_code()

    assert observed[
        "activation_widget_value_at_launch"
    ] == ""

    assert bridge.launch_calls == [
        ACTIVATION_CODE,
    ]



def test_successful_launch_withdraws_then_destroys_bootstrap_window(
    monkeypatch,
) -> None:
    (
        window,
        bridge,
        root,
        activation_var,
        status_var,
        button,
    ) = _window_for_submission(
        monkeypatch
    )

    window._submit_activation_code()

    assert bridge.launch_calls == [
        ACTIVATION_CODE,
    ]

    assert (
        activation_var.value
        == ""
    )

    assert (
        "withdraw"
        in root.calls
    )

    assert (
        "destroy"
        in root.calls
    )

    assert (
        root.calls.index(
            "withdraw"
        )
        < root.calls.index(
            "destroy"
        )
    )

    assert (
        status_var.value
        == "Starting TODOBA Setup..."
    )

    assert (
        {
            "state": "disabled",
        }
        in button.states
    )



def test_failed_launch_restores_window_with_generic_error_only(
    monkeypatch,
) -> None:
    sensitive_exception = (
        RuntimeError(
            "server rejected "
            + ACTIVATION_CODE
        )
    )

    bridge = (
        FakeBridge(
            failure=(
                sensitive_exception
            )
        )
    )

    (
        window,
        _bridge,
        root,
        activation_var,
        status_var,
        button,
    ) = _window_for_submission(
        monkeypatch,
        bridge=bridge,
    )

    window._submit_activation_code()

    assert bridge.launch_calls == [
        ACTIVATION_CODE,
    ]

    assert (
        activation_var.value
        == ""
    )

    assert (
        "withdraw"
        in root.calls
    )

    assert (
        "deiconify"
        in root.calls
    )

    assert (
        "destroy"
        not in root.calls
    )

    assert (
        button.states[-1]
        == {
            "state": "normal",
        }
    )

    assert (
        status_var.value
        == (
            "TODOBA Setup could not continue. "
            "Please verify your Activation Code "
            "and try again."
        )
    )

    assert (
        ACTIVATION_CODE
        not in status_var.value
    )

    assert (
        "server rejected"
        not in status_var.value
    )



def test_gui_exposes_no_challenge_copy_ceremony(
) -> None:
    methods = {
        name
        for name in dir(
            customer_setup_module
            .CustomerSetupBootstrapWindow
        )
        if not name.startswith(
            "__"
        )
    }

    assert (
        "_copy_challenge"
        not in methods
    )

    assert (
        "_submit_authorization_code"
        not in methods
    )

    assert (
        "_require_authorization_code_var"
        not in methods
    )

    assert (
        "_submit_activation_code"
        in methods
    )



def test_main_returns_zero_on_success(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        customer_setup_module,
        "run_production_customer_setup",
        lambda: None,
    )

    assert (
        customer_setup_module.main()
        == 0
    )


def test_main_fails_closed_with_generic_customer_message(
    monkeypatch,
) -> None:
    secret = (
        "PRIVATE-STARTUP-DETAIL"
    )

    def fail():
        raise RuntimeError(
            secret
        )

    monkeypatch.setattr(
        customer_setup_module,
        "run_production_customer_setup",
        fail,
    )

    shown = {}

    monkeypatch.setattr(
        customer_setup_module.messagebox,
        "showerror",
        lambda title, message: (
            shown.update(
                {
                    "title": title,
                    "message": message,
                }
            )
        ),
    )

    assert (
        customer_setup_module.main()
        == 1
    )

    assert (
        secret
        not in shown[
            "message"
        ]
    )

    assert (
        shown[
            "message"
        ]
        == customer_setup_module._GENERIC_STARTUP_ERROR
    )


def test_gui_uses_only_hidden_activation_bridge_contract(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup.py"
    )

    source = path.read_text(
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
            == "CustomerSetupBootstrapWindow"
        )
    ]

    assert len(
        classes
    ) == 1

    attribute_names = {
        node.attr
        for node in ast.walk(
            classes[0]
        )
        if isinstance(
            node,
            ast.Attribute,
        )
    }

    assert (
        "launch"
        in attribute_names
    )

    assert (
        "code_challenge_s256"
        not in attribute_names
    )

    assert (
        "authorization_code"
        not in attribute_names
    )

    assert (
        "_code_verifier"
        not in attribute_names
    )

    assert (
        "code_verifier"
        not in attribute_names
    )



def test_source_has_no_persistence_or_logging_authority(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup.py"
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
        "logging",
        "json",
        "sqlite3",
    }.isdisjoint(
        imported_roots
    )

    called_names = set()

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if isinstance(
            node.func,
            ast.Name,
        ):
            called_names.add(
                node.func.id
            )

        elif isinstance(
            node.func,
            ast.Attribute,
        ):
            called_names.add(
                node.func.attr
            )

    forbidden = {
        "print",
        "open",
        "write",
        "write_text",
        "write_bytes",
        "dump",
        "dumps",
        "initialize_empty",
        "open_existing",
        "register",
    }

    assert forbidden.isdisjoint(
        called_names
    )


def test_entrypoint_has_no_server_or_business_authority(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup.py"
    )

    source = path.read_text(
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

    commercial_modules = {
        value
        for value in imported_modules
        if value.startswith(
            "backend.commercial."
        )
    }

    assert commercial_modules == {
        (
            "backend.commercial."
            "customer_setup_bootstrap_acquisition"
        ),
        (
            "backend.commercial."
            "customer_setup_access_code_http_client"
        ),
        (
            "backend.commercial."
            "customer_setup_access_code_bootstrap_bridge"
        ),
    }

    assert {
        "fastapi",
        "uvicorn",
    }.isdisjoint(
        {
            value.split(
                ".",
                1,
            )[0]
            for value in imported_modules
        }
    )

    executable_identifiers = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Name,
        ):
            executable_identifiers.add(
                node.id
            )

        elif isinstance(
            node,
            ast.Attribute,
        ):
            executable_identifiers.add(
                node.attr
            )

    for forbidden in (
        "customer_id",
        "setup_activation_id",
        "deployment_id",
        "payment_id",
        "subscription_id",
        "agent_id",
    ):
        assert (
            forbidden
            not in executable_identifiers
        )



def test_entrypoint_imports_authoritative_cloud_config(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    config_imports = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
            == "backend.config"
        )
    ]

    assert len(
        config_imports
    ) == 1

    imported_names = {
        alias.name
        for alias in config_imports[
            0
        ].names
    }

    assert imported_names == {
        "TODOBA_CLOUD_BASE_URL",
    }


def test_entrypoint_does_not_define_cloud_url_literal(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "https://api.todobagroup.com"
        not in source
    )


def test_gui_source_contains_locked_single_code_customer_copy(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "Welcome to TODOBA Trading"
        in source
    )

    assert (
        "Enter your Activation Code to begin."
        in source
    )

    assert (
        'text="Activation Code"'
        in source
    )

    assert (
        'text="Start Setup"'
        in source
    )

    assert (
        'text="Setup Challenge"'
        not in source
    )

    assert (
        'text="Authorization Code"'
        not in source
    )

    assert (
        "_copy_challenge"
        not in source
    )

    assert (
        "_submit_authorization_code"
        not in source
    )



def test_entrypoint_has_no_authorization_code_output_channel(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    assert not any(
        isinstance(
            node,
            ast.Call,
        )
        and isinstance(
            node.func,
            ast.Name,
        )
        and node.func.id
        == "print"
        for node in ast.walk(tree)
    )


def test_existing_setup_owners_are_not_imported_directly(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "customer_setup_bootstrap_coordinator"
        not in source
    )

    assert (
        "customer_setup_launcher"
        not in source
    )

    assert (
        "customer_setup_gui_shell"
        not in source
    )


def test_production_entrypoint_has_expected_top_level_functions(
) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "customer_setup.py"
    )

    source = path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    top_level_functions = {
        node.name
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
    }

    assert top_level_functions == {
        "_resolve_roaming_appdata_path",
        "run_production_customer_setup",
        "main",
    }


def test_bootstrap_window_public_surface_is_minimal(
) -> None:
    public = {
        name
        for name in dir(
            customer_setup_module.CustomerSetupBootstrapWindow
        )
        if not name.startswith(
            "_"
        )
    }

    assert public == {
        "build_window",
        "run",
    }
