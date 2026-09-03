"""
Owner tests for TODOBA Customer Setup GUI Shell.
"""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.commercial.customer_setup_gui_shell as module
from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallerService,
)
from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightService,
)
from backend.commercial.customer_setup_application_controller import (
    CustomerSetupApplicationController,
    CustomerSetupApplicationResult,
    CustomerSetupInstallationOption,
)
from backend.commercial.customer_setup_gui_shell import (
    CustomerSetupGuiShell,
    WELCOME_HEADLINE,
    WELCOME_SUBTITLE,
    WINDOW_TITLE,
)
from backend.commercial.customer_setup_http_client import (
    CustomerSetupHttpClient,
)
from backend.commercial.customer_setup_orchestration_service import (
    CustomerSetupOrchestrationService,
)


class FakeStringVar:
    def __init__(
        self,
        *,
        value="",
    ):
        self.value = value

    def set(
        self,
        value,
    ):
        self.value = value

    def get(
        self,
    ):
        return self.value


class FakeWidget:
    def __init__(
        self,
        parent=None,
        **kwargs,
    ):
        self.parent = parent
        self.options = dict(
            kwargs
        )
        self.pack_calls = []

    def pack(
        self,
        **kwargs,
    ):
        self.pack_calls.append(
            kwargs
        )
        return self

    def configure(
        self,
        **kwargs,
    ):
        self.options.update(
            kwargs
        )

    config = configure

    def cget(
        self,
        key,
    ):
        return self.options.get(
            key
        )


class FakeListbox(
    FakeWidget
):
    def __init__(
        self,
        parent=None,
        **kwargs,
    ):
        super().__init__(
            parent,
            **kwargs,
        )
        self.items = []
        self.selection = ()
        self.bindings = {}

    def bind(
        self,
        event,
        callback,
    ):
        self.bindings[
            event
        ] = callback

    def delete(
        self,
        start,
        end,
    ):
        del start
        del end
        self.items = []
        self.selection = ()

    def insert(
        self,
        index,
        value,
    ):
        del index
        self.items.append(
            value
        )

    def curselection(
        self,
    ):
        return self.selection

    def selection_set(
        self,
        index,
    ):
        self.selection = (
            index,
        )


class FakeRoot(
    FakeWidget
):
    def __init__(
        self,
    ):
        super().__init__(
            None
        )
        self.window_title = None
        self.window_geometry = None
        self.resizable_value = None
        self.mainloop_called = False
        self.destroyed = False

    def title(
        self,
        value,
    ):
        self.window_title = value

    def geometry(
        self,
        value,
    ):
        self.window_geometry = value

    def resizable(
        self,
        width,
        height,
    ):
        self.resizable_value = (
            width,
            height,
        )

    def mainloop(
        self,
    ):
        self.mainloop_called = True

    def quit(
        self,
    ):
        self.quit_called = True

    def destroy(
        self,
    ):
        self.destroyed = True


def _install_fake_tk(
    monkeypatch,
):
    fake_tk = SimpleNamespace(
        Tk=FakeRoot,
        StringVar=FakeStringVar,
        Listbox=FakeListbox,
        END="end",
    )

    fake_ttk = SimpleNamespace(
        Frame=FakeWidget,
        Label=FakeWidget,
        Button=FakeWidget,
    )

    monkeypatch.setattr(
        module,
        "tk",
        fake_tk,
    )
    monkeypatch.setattr(
        module,
        "ttk",
        fake_ttk,
    )


def _preflight_service(
):
    fake_mt5 = SimpleNamespace(
        initialize=lambda **kwargs: True,
        shutdown=lambda: None,
        terminal_info=lambda: None,
        account_info=lambda: None,
        ACCOUNT_MARGIN_MODE_RETAIL_HEDGING=2,
    )

    return CustomerMT5SetupPreflightService(
        mt5_module=fake_mt5
    )


def _controller(
):
    preflight_service = (
        _preflight_service()
    )

    http_client = CustomerSetupHttpClient(
        setup_base_url=(
            "https://api.example.test"
        ),
        setup_handoff_credential=(
            "test-secret"
        ),
    )

    orchestration_service = (
        CustomerSetupOrchestrationService(
            setup_http_client=(
                http_client
            ),
            ex5_installer_service=(
                CustomerMT5EX5InstallerService()
            ),
        )
    )

    return CustomerSetupApplicationController(
        mt5_preflight_service=(
            preflight_service
        ),
        setup_orchestration_service=(
            orchestration_service
        ),
    )


def _shell(
    tmp_path: Path,
) -> CustomerSetupGuiShell:
    return CustomerSetupGuiShell(
        controller=_controller(),
        roaming_appdata_path=(
            tmp_path
        ),
    )


def _option(
    name: str = "MT5",
) -> CustomerSetupInstallationOption:
    return CustomerSetupInstallationOption(
        installation_path=(
            f"C:\\{name}"
        ),
        terminal_path=(
            f"C:\\{name}\\terminal64.exe"
        ),
        portable=False,
    )


def _build(
    tmp_path: Path,
    monkeypatch,
    *,
    options=(),
):
    _install_fake_tk(
        monkeypatch
    )

    shell = _shell(
        tmp_path
    )

    monkeypatch.setattr(
        shell._controller,
        "discover_standard_installations",
        lambda **kwargs: options,
    )

    root = shell.build_window()

    return (
        shell,
        root,
    )


def test_locked_customer_welcome_copy() -> None:
    assert (
        WINDOW_TITLE
        == 'TODOBA Trading AI Setup'
    )
    assert (
        WELCOME_HEADLINE
        == "Welcome to TODOBA Trading"
    )
    assert (
        WELCOME_SUBTITLE
        == (
            'Set up TODOBA Trading AI for your MetaTrader 5 account.'
        )
    )


def test_constructor_requires_application_controller(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match="controller must be",
    ):
        CustomerSetupGuiShell(
            controller=object(),
            roaming_appdata_path=(
                tmp_path
            ),
        )


def test_constructor_requires_roaming_path() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "roaming_appdata_path must be Path"
        ),
    ):
        CustomerSetupGuiShell(
            controller=_controller(),
            roaming_appdata_path="bad",
        )


def test_build_window_has_todoba_identity_and_discovers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option()

    shell, root = _build(
        tmp_path,
        monkeypatch,
        options=(
            option,
        ),
    )

    assert (
        root.window_title
        == 'TODOBA Trading AI Setup'
    )
    assert (
        root.window_geometry
        == "700x500"
    )
    assert (
        root.resizable_value
        == (
            False,
            False,
        )
    )

    assert shell._options == (
        option,
    )

    assert shell._installation_list.items == [
        "MetaTrader 5 — C:\\MT5"
    ]


def test_empty_discovery_is_customer_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shell, _ = _build(
        tmp_path,
        monkeypatch,
        options=(),
    )

    assert shell._options == ()
    assert (
        shell._installation_list.items
        == []
    )
    assert (
        'No supported MetaTrader 5 installation was found'
        in shell._status_var.get()
    )
    assert (
        shell._install_button.cget(
            "state"
        )
        == "disabled"
    )


def test_selection_enables_install(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shell, _ = _build(
        tmp_path,
        monkeypatch,
        options=(
            _option(),
        ),
    )

    shell._installation_list.selection_set(
        0
    )
    shell._on_selection_changed()

    assert (
        shell._install_button.cget(
            "state"
        )
        == "normal"
    )


def test_no_selection_does_not_run_setup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shell, _ = _build(
        tmp_path,
        monkeypatch,
        options=(
            _option(),
        ),
    )

    called = []

    monkeypatch.setattr(
        shell._controller,
        "run_selected",
        lambda **kwargs: called.append(
            kwargs
        ),
    )

    shell.install_selected()

    assert called == []
    assert (
        'Select a MetaTrader 5 installation'
        in shell._status_var.get()
    )


def test_build_pending_requires_customer_continue(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option()

    shell, _ = _build(
        tmp_path,
        monkeypatch,
        options=(
            option,
        ),
    )

    calls = []

    def run_selected(
        *,
        option,
    ):
        calls.append(
            option
        )

        return CustomerSetupApplicationResult(
            status="build_pending",
            terminal_path=(
                option.terminal_path
            ),
            login=12345678,
            server="Broker-Server",
            account_fingerprint=(
                "Broker-Server:12345678"
            ),
        )

    monkeypatch.setattr(
        shell._controller,
        "run_selected",
        run_selected,
    )

    shell._installation_list.selection_set(
        0
    )

    shell.install_selected()

    assert calls == [
        option
    ]

    assert (
        shell._install_button.cget(
            "state"
        )
        == "normal"
    )

    assert (
        shell._install_button.cget(
            "text"
        )
        == "Continue"
    )

    assert (
        "Preparing TODOBA Trading AI"
        in shell._status_var.get()
    )

    assert (
        "HEDGING"
        in shell._account_var.get()
    )

    assert (
        "Broker-Server / 12345678"
        in shell._account_var.get()
    )

    assert (
        shell._finish_button.cget(
            "state"
        )
        == "disabled"
    )



def test_build_pending_does_not_auto_poll(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shell, _ = _build(
        tmp_path,
        monkeypatch,
        options=(
            _option(),
        ),
    )

    count = {
        "value": 0,
    }

    def run_selected(
        *,
        option,
    ):
        count[
            "value"
        ] += 1

        return CustomerSetupApplicationResult(
            status="build_pending",
            terminal_path=(
                option.terminal_path
            ),
            login=12345678,
            server="Broker-Server",
            account_fingerprint=(
                "Broker-Server:12345678"
            ),
        )

    monkeypatch.setattr(
        shell._controller,
        "run_selected",
        run_selected,
    )

    shell._installation_list.selection_set(
        0
    )
    shell.install_selected()

    assert count["value"] == 1


def test_installed_enables_finish_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option()

    shell, root = _build(
        tmp_path,
        monkeypatch,
        options=(
            option,
        ),
    )

    monkeypatch.setattr(
        shell._controller,
        "run_selected",
        lambda **kwargs: (
            CustomerSetupApplicationResult(
                status="installed",
                terminal_path=(
                    option.terminal_path
                ),
                login=12345678,
                server="Broker-Server",
                account_fingerprint=(
                    "Broker-Server:12345678"
                ),
                installed_path=(
                    "C:\\MT5Data\\MQL5\\Experts"
                    "\\TODOBA_Trusted_Agent.ex5"
                ),
                already_present=False,
            )
        ),
    )

    shell._installation_list.selection_set(
        0
    )
    shell.install_selected()

    assert (
        shell._status_var.get()
        == 'TODOBA Trading AI was installed successfully.'
    )
    assert (
        shell._installation_list.cget(
            "state"
        )
        == "disabled"
    )
    assert (
        shell._refresh_button.cget(
            "state"
        )
        == "disabled"
    )
    assert (
        shell._install_button.cget(
            "state"
        )
        == "disabled"
    )
    assert (
        shell._finish_button.cget(
            "state"
        )
        == "normal"
    )

    finish_command = (
        shell._finish_button.cget(
            "command"
        )
    )
    finish_command()

    assert root.quit_called is True

    assert root.destroyed is True


def test_finish_copy_does_not_claim_runtime_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option()

    shell, _ = _build(
        tmp_path,
        monkeypatch,
        options=(
            option,
        ),
    )

    monkeypatch.setattr(
        shell._controller,
        "run_selected",
        lambda **kwargs: (
            CustomerSetupApplicationResult(
                status="installed",
                terminal_path=(
                    option.terminal_path
                ),
                login=12345678,
                server="Broker-Server",
                account_fingerprint=(
                    "Broker-Server:12345678"
                ),
                installed_path=(
                    "C:\\installed.ex5"
                ),
                already_present=False,
            )
        ),
    )

    shell._installation_list.selection_set(
        0
    )
    shell.install_selected()

    customer_text = (
        shell._status_var.get()
        + " "
        + shell._account_var.get()
    ).lower()

    for forbidden in (
        "agent running",
        "online",
        "trading ready",
        "auto trading",
    ):
        assert forbidden not in customer_text


def test_controller_failure_is_customer_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option()

    shell, _ = _build(
        tmp_path,
        monkeypatch,
        options=(
            option,
        ),
    )

    secret_internal_message = (
        "private-secret-value"
    )

    def fail(
        **kwargs,
    ):
        del kwargs
        raise RuntimeError(
            secret_internal_message
        )

    monkeypatch.setattr(
        shell._controller,
        "run_selected",
        fail,
    )

    shell._installation_list.selection_set(
        0
    )
    shell.install_selected()

    assert (
        secret_internal_message
        not in shell._status_var.get()
    )
    assert (
        shell._status_var.get()
        == (
            'Setup could not complete this step. Please try again.'
        )
    )


def test_discovery_failure_is_customer_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_tk(
        monkeypatch
    )

    shell = _shell(
        tmp_path
    )

    monkeypatch.setattr(
        shell._controller,
        "discover_standard_installations",
        lambda **kwargs: (
            (_ for _ in ()).throw(
                RuntimeError(
                    "private-discovery-detail"
                )
            )
        ),
    )

    shell.build_window()

    assert (
        shell._status_var.get()
        == (
            'Setup could not complete this step. Please try again.'
        )
    )
    assert (
        "private-discovery-detail"
        not in shell._status_var.get()
    )


def test_window_cannot_be_built_twice(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shell, _ = _build(
        tmp_path,
        monkeypatch,
        options=(),
    )

    with pytest.raises(
        RuntimeError,
        match="already built",
    ):
        shell.build_window()


def test_run_starts_mainloop(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_tk(
        monkeypatch
    )

    shell = _shell(
        tmp_path
    )

    monkeypatch.setattr(
        shell._controller,
        "discover_standard_installations",
        lambda **kwargs: (),
    )

    shell.run()

    assert (
        shell._root.mainloop_called
        is True
    )


def test_owner_is_presentation_only() -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_gui_shell.py"
    )

    source = source_path.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source
    )

    imported_modules: set[str] = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imported_modules.update(
                alias.name
                for alias in node.names
            )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module is not None:
                imported_modules.add(
                    node.module
                )

    assert "tkinter" in imported_modules

    forbidden_modules = (
        "httpx",
        "fastapi",
        "backend.main",
        "MetaTrader5",
        "dotenv",
    )

    for forbidden in forbidden_modules:
        assert forbidden not in imported_modules

    forbidden_tokens = (
        "CustomerSetupHttpClient",
        "CustomerSetupEntryGrant",
        "setup_handoff_credential",
        "setup_base_url",
        "TODOBA_CLOUD_BASE_URL",
        "os.environ",
        "load_dotenv",
        "time.sleep",
        "asyncio.sleep",
        "NamedTemporaryFile",
        "os.rename",
        "initialize_empty(",
        "storage_path",
    )

    for token in forbidden_tokens:
        assert token not in source


def test_recoverable_setup_error_uses_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    option = _option()

    shell, _ = _build(
        tmp_path,
        monkeypatch,
        options=(
            option,
        ),
    )

    def fail_setup(
        *,
        option,
    ):
        del option

        raise RuntimeError(
            "recoverable failure"
        )

    monkeypatch.setattr(
        shell._controller,
        "run_selected",
        fail_setup,
    )

    shell._installation_list.selection_set(
        0
    )

    shell.install_selected()

    assert (
        shell._install_button.cget(
            "state"
        )
        == "normal"
    )

    assert (
        shell._install_button.cget(
            "text"
        )
        == "Retry"
    )

    assert (
        shell._status_var.get()
        == (
            "Setup could not complete this step. "
            "Please try again."
        )
    )
