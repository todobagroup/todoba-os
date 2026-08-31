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


def _window_for_submission(
    monkeypatch,
    *,
    authorization_code=AUTHORIZATION_CODE,
    acquisition=None,
):
    if acquisition is None:
        acquisition = FakeAcquisition()

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupBootstrapAcquisition",
        FakeAcquisition,
    )

    window = (
        customer_setup_module
        .CustomerSetupBootstrapWindow(
            acquisition=acquisition,
        )
    )

    root = FakeRoot()

    authorization_var = (
        FakeVariable(
            authorization_code
        )
    )

    status_var = (
        FakeVariable()
    )

    button = (
        FakeButton()
    )

    window._root = root
    window._authorization_code_var = (
        authorization_var
    )
    window._status_var = (
        status_var
    )
    window._continue_button = button

    return (
        window,
        acquisition,
        root,
        authorization_var,
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

    class FakeWindow:
        def __init__(
            self,
            *,
            acquisition,
        ):
            observed[
                "window_acquisition"
            ] = acquisition

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

    assert (
        observed[
            "acquisition"
        ][
            "setup_base_url"
        ]
        == customer_setup_module.TODOBA_CLOUD_BASE_URL
    )

    assert (
        customer_setup_module.TODOBA_CLOUD_BASE_URL
        == "https://api.todobagroup.com"
    )

    assert (
        observed[
            "acquisition"
        ][
            "mt5_module"
        ]
        is fake_mt5
    )

    assert (
        observed[
            "acquisition"
        ][
            "roaming_appdata_path"
        ]
        == Path(APPDATA_PATH)
    )

    assert (
        observed[
            "window_acquisition"
        ]
        is not None
    )

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


def test_bootstrap_window_requires_acquisition_owner(
    monkeypatch,
) -> None:
    class RequiredAcquisition:
        pass

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupBootstrapAcquisition",
        RequiredAcquisition,
    )

    with pytest.raises(
        TypeError,
        match=(
            "acquisition must be "
            "CustomerSetupBootstrapAcquisition"
        ),
    ):
        customer_setup_module.CustomerSetupBootstrapWindow(
            acquisition=object(),
        )


def test_empty_authorization_code_never_crosses_boundary(
    monkeypatch,
) -> None:
    (
        window,
        acquisition,
        root,
        authorization_var,
        status_var,
        button,
    ) = _window_for_submission(
        monkeypatch,
        authorization_code="   ",
    )

    window._submit_authorization_code()

    assert (
        acquisition.launch_calls
        == []
    )

    assert (
        root.calls
        == []
    )

    assert (
        authorization_var.value
        == "   "
    )

    assert (
        "Enter the Authorization Code"
        in status_var.value
    )

    assert button.states == []


def test_authorization_code_is_stripped_before_launch(
    monkeypatch,
) -> None:
    (
        window,
        acquisition,
        _root,
        _authorization_var,
        _status_var,
        _button,
    ) = _window_for_submission(
        monkeypatch,
        authorization_code=(
            f"  {AUTHORIZATION_CODE}  "
        ),
    )

    window._submit_authorization_code()

    assert (
        acquisition.launch_calls
        == [
            AUTHORIZATION_CODE,
        ]
    )


def test_plaintext_authorization_widget_is_cleared_before_launch(
    monkeypatch,
) -> None:
    observed = {}

    class InspectingAcquisition(
        FakeAcquisition
    ):
        def launch(
            self,
            *,
            authorization_code,
        ):
            observed[
                "authorization_widget_value_at_launch"
            ] = (
                authorization_var.value
            )

            super().launch(
                authorization_code=(
                    authorization_code
                )
            )

    acquisition = (
        InspectingAcquisition()
    )

    monkeypatch.setattr(
        customer_setup_module,
        "CustomerSetupBootstrapAcquisition",
        InspectingAcquisition,
    )

    window = (
        customer_setup_module
        .CustomerSetupBootstrapWindow(
            acquisition=acquisition,
        )
    )

    root = FakeRoot()

    authorization_var = (
        FakeVariable(
            AUTHORIZATION_CODE
        )
    )

    window._root = root
    window._authorization_code_var = (
        authorization_var
    )
    window._status_var = FakeVariable()
    window._continue_button = FakeButton()

    window._submit_authorization_code()

    assert (
        observed[
            "authorization_widget_value_at_launch"
        ]
        == ""
    )

    assert (
        authorization_var.set_values[0]
        == ""
    )


def test_successful_launch_withdraws_then_destroys_bootstrap_window(
    monkeypatch,
) -> None:
    (
        window,
        acquisition,
        root,
        _authorization_var,
        status_var,
        button,
    ) = _window_for_submission(
        monkeypatch
    )

    monkeypatch.setattr(
        customer_setup_module,
        "tk",
        SimpleNamespace(
            DISABLED="disabled",
            NORMAL="normal",
        ),
    )

    window._submit_authorization_code()

    assert (
        acquisition.launch_calls
        == [
            AUTHORIZATION_CODE,
        ]
    )

    assert root.calls == [
        "update_idletasks",
        "withdraw",
        "destroy",
    ]

    assert button.states == [
        {
            "state": "disabled",
        },
    ]

    assert (
        status_var.value
        == "Connecting securely to TODOBA..."
    )


def test_failed_launch_restores_window_with_generic_error_only(
    monkeypatch,
) -> None:
    sensitive_exception = (
        RuntimeError(
            "server rejected "
            + AUTHORIZATION_CODE
        )
    )

    acquisition = (
        FakeAcquisition(
            failure=sensitive_exception,
        )
    )

    (
        window,
        _acquisition,
        root,
        authorization_var,
        status_var,
        button,
    ) = _window_for_submission(
        monkeypatch,
        acquisition=acquisition,
    )

    monkeypatch.setattr(
        customer_setup_module,
        "tk",
        SimpleNamespace(
            DISABLED="disabled",
            NORMAL="normal",
        ),
    )

    shown = {}

    def showerror(
        title,
        message,
        **kwargs,
    ):
        shown[
            "title"
        ] = title

        shown[
            "message"
        ] = message

        shown[
            "kwargs"
        ] = kwargs

    monkeypatch.setattr(
        customer_setup_module.messagebox,
        "showerror",
        showerror,
    )

    window._submit_authorization_code()

    assert root.calls == [
        "update_idletasks",
        "withdraw",
        "deiconify",
    ]

    assert button.states == [
        {
            "state": "disabled",
        },
        {
            "state": "normal",
        },
    ]

    assert (
        authorization_var.value
        == ""
    )

    assert (
        AUTHORIZATION_CODE
        not in status_var.value
    )

    assert (
        AUTHORIZATION_CODE
        not in shown[
            "message"
        ]
    )

    assert (
        str(
            sensitive_exception
        )
        not in shown[
            "message"
        ]
    )

    assert (
        shown[
            "message"
        ]
        == customer_setup_module._GENERIC_LAUNCH_ERROR
    )


def test_copy_challenge_copies_only_public_challenge(
    monkeypatch,
) -> None:
    (
        window,
        acquisition,
        root,
        _authorization_var,
        status_var,
        _button,
    ) = _window_for_submission(
        monkeypatch
    )

    window._copy_challenge()

    assert (
        root.clipboard_value
        == SETUP_CHALLENGE
    )

    assert root.calls == [
        "clipboard_clear",
        "clipboard_append",
        "update",
    ]

    assert (
        status_var.value
        == "Setup Challenge copied."
    )

    assert (
        root.clipboard_value
        == acquisition.code_challenge_s256
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


def test_source_uses_only_public_acquisition_contract(
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

    attribute_names = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.Attribute,
        )
    }

    assert (
        "_code_verifier"
        not in attribute_names
    )

    assert (
        "code_verifier"
        not in attribute_names
    )

    assert (
        "code_challenge_s256"
        in attribute_names
    )

    assert (
        "launch"
        in attribute_names
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

    for node in ast.walk(tree):
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
    }

    assert (
        "backend.main"
        not in imported_modules
    )

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

    forbidden_authorities = (
        "CustomerIdentityRegistry",
        "CustomerDeployment",
        "CustomerOnboardingService",
        "CustomerSetupActivationService",
        "CustomerSetupLaunchCredentialService",
        "CustomerSetupBootstrapAuthorizationService",
        "CustomerSetupBootstrapAuthorizationStore",
        "CustomerSetupBootstrapCoordinator",
        "CustomerSetupLauncher",
        "customer_id",
        "deployment_id",
        "agent_id",
        "payment_id",
        "subscription_id",
    )

    for token in forbidden_authorities:
        assert token not in source


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


def test_gui_source_contains_locked_customer_copy(
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
        "Setup Challenge"
        in source
    )

    assert (
        "Authorization Code"
        in source
    )

    assert (
        "Copy Challenge"
        in source
    )

    assert (
        "Continue"
        in source
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
