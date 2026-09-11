from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.commercial.customer_vps_connect_gui_shell as gui_module

from backend.commercial.customer_vps_connect_application_shell import (
    CustomerVPSConnectApplicationShell,
)

from backend.commercial.customer_vps_connect_gui_shell import (
    CustomerVPSConnectGuiShell,
    WINDOW_TITLE,
)


ROAMING = Path(
    r"C:\Users\Customer\AppData\Roaming"
)

ACTIVATION_CODE = (
    "setup-activation-c7b-secret"
)

OPTION_A = SimpleNamespace(
    installation_path=r"C:\MT5-A",
)

OPTION_B = SimpleNamespace(
    installation_path=r"D:\MT5-B",
)


class FakeApplicationShell(
    CustomerVPSConnectApplicationShell
):
    def __init__(
        self,
        *,
        options=(),
        proof_statuses=(),
        finish_error=False,
    ):
        self.options = tuple(options)
        self.proof_statuses = list(
            proof_statuses
        )
        self.finish_error = finish_error

        self.open_calls = 0
        self.detect_calls = []
        self.connect_calls = []
        self.verify_calls = 0
        self.finish_calls = 0

    def open(self):
        self.open_calls += 1

    def detect(
        self,
        *,
        roaming_appdata_path,
    ):
        self.detect_calls.append(
            roaming_appdata_path
        )

        return SimpleNamespace(
            installations=self.options,
        )

    def connect(
        self,
        *,
        activation_code,
        option,
    ):
        self.connect_calls.append(
            (
                activation_code,
                option,
            )
        )

        return SimpleNamespace(
            status="grant_ready",
        )

    def verify(self):
        self.verify_calls += 1

        return SimpleNamespace(
            status=self.proof_statuses.pop(0),
        )

    def finish(self):
        self.finish_calls += 1

        if self.finish_error:
            raise RuntimeError(
                "internal finish failure"
            )


class FakeRoot:
    def __init__(self):
        self.window_title = None
        self.geometry_value = None
        self.resizable_value = None
        self.protocols = {}
        self.mainloop_calls = 0
        self.quit_calls = 0
        self.destroy_calls = 0

    def title(
        self,
        value,
    ):
        self.window_title = value

    def geometry(
        self,
        value,
    ):
        self.geometry_value = value

    def resizable(
        self,
        width,
        height,
    ):
        self.resizable_value = (
            width,
            height,
        )

    def protocol(
        self,
        name,
        callback,
    ):
        self.protocols[name] = callback

    def mainloop(self):
        self.mainloop_calls += 1

    def quit(self):
        self.quit_calls += 1

    def destroy(self):
        self.destroy_calls += 1


class FakeWidget:
    instances = []

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        self.text = kwargs.get(
            "text"
        )

        self.state = kwargs.get(
            "state",
            "normal",
        )

        self.command = kwargs.get(
            "command"
        )

        self.values = tuple(
            kwargs.get(
                "values",
                (),
            )
        )

        self.value = ""
        self.current_index = -1
        self.visible = False

        type(self).instances.append(
            self
        )

    def pack(
        self,
        *args,
        **kwargs,
    ):
        self.visible = True
        return None

    def pack_forget(
        self,
    ):
        self.visible = False
        return None

    def grid(
        self,
        *args,
        **kwargs,
    ):
        return None

    def columnconfigure(
        self,
        *args,
        **kwargs,
    ):
        return None

    def configure(
        self,
        **kwargs,
    ):
        if "text" in kwargs:
            self.text = kwargs[
                "text"
            ]

        if "state" in kwargs:
            self.state = kwargs[
                "state"
            ]

        if "values" in kwargs:
            self.values = tuple(
                kwargs["values"]
            )

    config = configure

    def cget(
        self,
        name,
    ):
        return getattr(
            self,
            name,
        )

    def get(self):
        return self.value

    def insert(
        self,
        index,
        value,
    ):
        self.value = value

    def delete(
        self,
        first,
        last=None,
    ):
        self.value = ""

    def current(
        self,
        index=None,
    ):
        if index is not None:
            self.current_index = index
            return None

        return self.current_index


def _patch_gui(
    monkeypatch,
):
    FakeWidget.instances = []

    root = FakeRoot()

    monkeypatch.setattr(
        gui_module.tk,
        "Tk",
        lambda: root,
    )

    monkeypatch.setattr(
        gui_module.ttk,
        "Frame",
        FakeWidget,
    )

    monkeypatch.setattr(
        gui_module.ttk,
        "Label",
        FakeWidget,
    )

    monkeypatch.setattr(
        gui_module.ttk,
        "Entry",
        FakeWidget,
    )

    monkeypatch.setattr(
        gui_module.ttk,
        "Combobox",
        FakeWidget,
    )

    monkeypatch.setattr(
        gui_module.ttk,
        "Button",
        FakeWidget,
    )

    return root


def _built_shell(
    monkeypatch,
    *,
    options=(),
    proof_statuses=(),
    finish_error=False,
):
    root = _patch_gui(
        monkeypatch
    )

    application = FakeApplicationShell(
        options=options,
        proof_statuses=proof_statuses,
        finish_error=finish_error,
    )

    shell = CustomerVPSConnectGuiShell(
        application_shell=application,
        roaming_appdata_path=ROAMING,
    )

    built = shell.build_window()

    assert built is root

    return (
        shell,
        application,
        root,
    )


def _button_with_text(
    text,
):
    matches = [
        widget
        for widget in FakeWidget.instances
        if widget.text == text
    ]

    assert len(matches) == 1
    return matches[0]


def test_single_primary_action_progresses_detect_connect_verify_finish(
    monkeypatch,
):
    (
        shell,
        _,
        _,
    ) = _built_shell(
        monkeypatch,
        options=(
            OPTION_A,
        ),
        proof_statuses=(
            "vps_online",
        ),
    )

    detect = _button_with_text("Detect")
    connect = _button_with_text("Connect")
    verify = _button_with_text("Verify")
    finish = _button_with_text("Finish")

    assert detect.visible is True
    assert connect.visible is False
    assert verify.visible is False
    assert finish.visible is False

    shell.detect_mt5()

    assert detect.visible is False
    assert connect.visible is True
    assert verify.visible is False
    assert finish.visible is False

    shell._activation_entry.insert(
        0,
        ACTIVATION_CODE,
    )
    shell.connect_selected()

    assert detect.visible is False
    assert connect.visible is False
    assert verify.visible is True
    assert finish.visible is False

    shell.verify_vps()

    assert detect.visible is False
    assert connect.visible is False
    assert verify.visible is False
    assert finish.visible is True


def test_build_opens_application_and_uses_standalone_window(
    monkeypatch,
):
    (
        shell,
        application,
        root,
    ) = _built_shell(
        monkeypatch,
    )

    assert shell is not None
    assert application.open_calls == 1

    assert root.window_title == (
        "TODOBA VPS Connect"
    )

    assert WINDOW_TITLE == (
        "TODOBA VPS Connect"
    )

    assert (
        "WM_DELETE_WINDOW"
        in root.protocols
    )

    assert (
        shell._connect_button
        .cget("state")
        == "disabled"
    )

    assert (
        shell._verify_button
        .cget("state")
        == "disabled"
    )

    assert (
        shell._finish_button
        .cget("state")
        == "disabled"
    )


def test_detect_populates_existing_mt5_options(
    monkeypatch,
):
    (
        shell,
        application,
        _,
    ) = _built_shell(
        monkeypatch,
        options=(
            OPTION_A,
            OPTION_B,
        ),
    )

    shell.detect_mt5()

    assert application.detect_calls == [
        ROAMING,
    ]

    assert shell._options == (
        OPTION_A,
        OPTION_B,
    )

    assert (
        shell._mt5_selector.current()
        == 0
    )

    assert (
        shell._connect_button
        .cget("state")
        == "normal"
    )


def test_no_mt5_keeps_connect_disabled(
    monkeypatch,
):
    (
        shell,
        _,
        _,
    ) = _built_shell(
        monkeypatch,
        options=(),
    )

    shell.detect_mt5()

    assert shell._options == ()

    assert (
        shell._connect_button
        .cget("state")
        == "disabled"
    )


def test_connect_passes_activation_once_and_clears_entry(
    monkeypatch,
):
    (
        shell,
        application,
        _,
    ) = _built_shell(
        monkeypatch,
        options=(
            OPTION_A,
        ),
    )

    shell.detect_mt5()

    shell._activation_entry.insert(
        0,
        ACTIVATION_CODE,
    )

    shell.connect_selected()

    assert application.connect_calls == [
        (
            ACTIVATION_CODE,
            OPTION_A,
        )
    ]

    assert (
        shell._activation_entry.get()
        == ""
    )

    assert (
        shell._verify_button
        .cget("state")
        == "normal"
    )

    assert (
        shell._finish_button
        .cget("state")
        == "disabled"
    )

    assert ACTIVATION_CODE not in repr(
        shell
    )

    for value in vars(
        shell
    ).values():
        assert value != ACTIVATION_CODE


def test_verify_pending_keeps_finish_disabled(
    monkeypatch,
):
    (
        shell,
        application,
        _,
    ) = _built_shell(
        monkeypatch,
        options=(
            OPTION_A,
        ),
        proof_statuses=(
            "vps_pending",
        ),
    )

    shell.detect_mt5()

    shell._activation_entry.insert(
        0,
        ACTIVATION_CODE,
    )

    shell.connect_selected()
    shell.verify_vps()

    assert application.verify_calls == 1

    assert (
        shell._finish_button
        .cget("state")
        == "disabled"
    )


def test_verify_online_enables_finish(
    monkeypatch,
):
    (
        shell,
        application,
        _,
    ) = _built_shell(
        monkeypatch,
        options=(
            OPTION_A,
        ),
        proof_statuses=(
            "vps_online",
        ),
    )

    shell.detect_mt5()

    shell._activation_entry.insert(
        0,
        ACTIVATION_CODE,
    )

    shell.connect_selected()
    shell.verify_vps()

    assert application.verify_calls == 1

    assert (
        shell._finish_button
        .cget("state")
        == "normal"
    )


def test_later_pending_reblocks_finish(
    monkeypatch,
):
    (
        shell,
        _,
        _,
    ) = _built_shell(
        monkeypatch,
        options=(
            OPTION_A,
        ),
        proof_statuses=(
            "vps_online",
            "vps_pending",
        ),
    )

    shell.detect_mt5()

    shell._activation_entry.insert(
        0,
        ACTIVATION_CODE,
    )

    shell.connect_selected()

    shell.verify_vps()

    assert (
        shell._finish_button
        .cget("state")
        == "normal"
    )

    shell.verify_vps()

    assert (
        shell._finish_button
        .cget("state")
        == "disabled"
    )


def test_finish_closes_naturally_only_after_core_accepts(
    monkeypatch,
):
    (
        shell,
        application,
        root,
    ) = _built_shell(
        monkeypatch,
        options=(
            OPTION_A,
        ),
        proof_statuses=(
            "vps_online",
        ),
    )

    shell.detect_mt5()

    shell._activation_entry.insert(
        0,
        ACTIVATION_CODE,
    )

    shell.connect_selected()
    shell.verify_vps()
    shell.finish()

    assert application.finish_calls == 1
    assert root.quit_calls == 1
    assert root.destroy_calls == 1


def test_blocked_finish_keeps_window_open(
    monkeypatch,
):
    (
        shell,
        application,
        root,
    ) = _built_shell(
        monkeypatch,
        options=(
            OPTION_A,
        ),
        finish_error=True,
    )

    shell.finish()

    assert application.finish_calls == 1
    assert root.quit_calls == 0
    assert root.destroy_calls == 0

    assert (
        shell._finish_button
        .cget("state")
        == "disabled"
    )


def test_windows_x_is_natural_cancel_not_fake_finish(
    monkeypatch,
):
    (
        shell,
        application,
        root,
    ) = _built_shell(
        monkeypatch,
    )

    callback = root.protocols[
        "WM_DELETE_WINDOW"
    ]

    callback()

    assert application.finish_calls == 0
    assert root.quit_calls == 1
    assert root.destroy_calls == 1


def test_run_uses_natural_tk_mainloop(
    monkeypatch,
):
    root = FakeRoot()

    application = (
        FakeApplicationShell()
    )

    shell = CustomerVPSConnectGuiShell(
        application_shell=application,
        roaming_appdata_path=ROAMING,
    )

    monkeypatch.setattr(
        shell,
        "build_window",
        lambda: root,
    )

    shell.run()

    assert root.mainloop_calls == 1


def test_gui_shell_has_presentation_authority_only():
    source = Path(
        "backend/commercial/"
        "customer_vps_connect_gui_shell.py"
    ).read_text(
        encoding="utf-8-sig",
    )

    assert (
        "CustomerVPSConnectApplicationShell"
        in source
    )

    for forbidden in (
        "customer_setup_gui_shell",
        "customer_vps_connect_core_orchestration_service",
        "customer_vps_connect_grant_http_client",
        "customer_vps_connect_live_proof_http_client",
        "customer_vps_connect_mt5_detection_service",
        "customer_vps_connect_mt5_account_identity_service",
        "BrokerStateStore",
        "MetaTrader5",
        "WebRequestUrl",
        "common.ini",
        "PyInstaller",
        "subprocess",
        "write_text",
        "write_bytes",
        "initialize_empty",
        "time.sleep",
        "asyncio.sleep",
        "threading",
        "while True",
        "terminate(",
        "kill(",
    ):
        assert forbidden not in source

def test_detect_projects_detector_installations_contract(
    monkeypatch,
):
    shell, application, _ = _built_shell(
        monkeypatch,
    )

    application.detect = lambda **_: SimpleNamespace(
        installations=(
            OPTION_A,
            OPTION_B,
        ),
    )

    shell.detect_mt5()

    assert shell._options == (
        OPTION_A,
        OPTION_B,
    )

    assert shell._mt5_selector.current() == 0

    assert (
        shell._connect_button.cget("state")
        == "normal"
    )


def test_runtime_ready_guides_migration_without_enabling_finish(
    monkeypatch,
):
    shell, _, _ = _built_shell(
        monkeypatch,
        options=(
            OPTION_A,
        ),
        proof_statuses=(
            "runtime_ready",
        ),
    )

    shell.detect_mt5()

    shell._activation_entry.insert(
        0,
        ACTIVATION_CODE,
    )

    shell.connect_selected()
    shell.verify_vps()

    assert (
        shell._finish_button.cget("state")
        == "disabled"
    )

    status_text = (
        shell._status_label.cget("text")
    )

    assert "ready on this MT5" in status_text
    assert "MetaTrader VPS migration" in status_text
