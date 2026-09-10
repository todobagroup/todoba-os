"""
Thin standalone presentation shell for TODOBA VPS Connect.
"""

from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import ttk

from backend.commercial.customer_vps_connect_application_shell import (
    CustomerVPSConnectApplicationShell,
)


WINDOW_TITLE = "TODOBA VPS Connect"


class CustomerVPSConnectGuiShell:
    """
    Present the reusable VPS Connect application flow.
    """

    def __init__(
        self,
        *,
        application_shell: CustomerVPSConnectApplicationShell,
        roaming_appdata_path: Path,
    ) -> None:
        if not isinstance(
            application_shell,
            CustomerVPSConnectApplicationShell,
        ):
            raise TypeError(
                "application_shell must be "
                "CustomerVPSConnectApplicationShell."
            )

        if not isinstance(
            roaming_appdata_path,
            Path,
        ):
            raise TypeError(
                "roaming_appdata_path must be Path."
            )

        self._application_shell = application_shell
        self._roaming_appdata_path = roaming_appdata_path

        self._root = None
        self._activation_entry = None
        self._mt5_selector = None
        self._detect_button = None
        self._connect_button = None
        self._verify_button = None
        self._finish_button = None
        self._status_label = None

        self._options: tuple[Any, ...] = ()

    def __repr__(
        self,
    ) -> str:
        return (
            "CustomerVPSConnectGuiShell("
            f"built={self._root is not None!r}, "
            f"options={len(self._options)!r})"
        )

    def run(
        self,
    ) -> None:
        root = self.build_window()
        root.mainloop()

    def build_window(
        self,
    ):
        if self._root is not None:
            raise RuntimeError(
                "VPS Connect window is already built."
            )

        self._application_shell.open()

        root = tk.Tk()

        root.title(
            WINDOW_TITLE
        )

        root.geometry(
            "720x520"
        )

        root.resizable(
            False,
            False,
        )

        self._root = root

        outer = ttk.Frame(
            root,
            padding=28,
        )
        outer.pack(
            fill="both",
            expand=True,
        )

        heading = ttk.Label(
            outer,
            text="TODOBA VPS Connect",
        )
        heading.pack(
            pady=(0, 8),
        )

        subtitle = ttk.Label(
            outer,
            text=(
                "Connect your MetaTrader 5 environment "
                "to TODOBA."
            ),
        )
        subtitle.pack(
            pady=(0, 24),
        )

        activation_label = ttk.Label(
            outer,
            text="Activation Code",
        )
        activation_label.pack(
            anchor="w",
        )

        self._activation_entry = ttk.Entry(
            outer,
            show="*",
        )
        self._activation_entry.pack(
            fill="x",
            pady=(4, 18),
        )

        mt5_label = ttk.Label(
            outer,
            text="MetaTrader 5",
        )
        mt5_label.pack(
            anchor="w",
        )

        self._mt5_selector = ttk.Combobox(
            outer,
            values=(),
            state="readonly",
        )
        self._mt5_selector.pack(
            fill="x",
            pady=(4, 18),
        )

        button_row = ttk.Frame(
            outer,
        )
        button_row.pack(
            fill="x",
            pady=(4, 18),
        )

        self._detect_button = ttk.Button(
            button_row,
            text="Detect",
            command=self.detect_mt5,
        )
        self._detect_button.pack(
            side="left",
        )

        self._connect_button = ttk.Button(
            button_row,
            text="Connect",
            command=self.connect_selected,
            state="disabled",
        )
        self._verify_button = ttk.Button(
            button_row,
            text="Verify",
            command=self.verify_vps,
            state="disabled",
        )
        self._finish_button = ttk.Button(
            button_row,
            text="Finish",
            command=self.finish,
            state="disabled",
        )
        self._status_label = ttk.Label(
            outer,
            text=(
                "Ready to detect MetaTrader 5."
            ),
        )
        self._status_label.pack(
            anchor="w",
            pady=(12, 0),
        )

        root.protocol(
            "WM_DELETE_WINDOW",
            self._close_window,
        )

        return root

    def detect_mt5(
        self,
    ) -> None:
        self._require_built()

        result = self._application_shell.detect(
            roaming_appdata_path=(
                self._roaming_appdata_path
            ),
        )

        options = tuple(
            getattr(
                result,
                "installations",
                (),
            )
        )

        self._options = options

        labels = tuple(
            self._option_label(option)
            for option in options
        )

        self._mt5_selector.configure(
            values=labels,
        )

        self._verify_button.configure(
            state="disabled",
        )

        self._finish_button.configure(
            state="disabled",
        )

        if options:
            self._mt5_selector.current(
                0
            )

            self._show_primary_action(
                "connect"
            )

            self._set_status(
                "MetaTrader 5 detected. Ready to connect."
            )
        else:
            self._show_primary_action(
                "detect"
            )

            self._set_status(
                "No supported MetaTrader 5 installation detected."
            )

    def connect_selected(
        self,
    ) -> None:
        self._require_built()

        if not self._options:
            self._connect_button.configure(
                state="disabled",
            )

            self._set_status(
                "Detect MetaTrader 5 before connecting."
            )
            return

        index = self._mt5_selector.current()

        if (
            not isinstance(index, int)
            or index < 0
            or index >= len(self._options)
        ):
            self._set_status(
                "Select a MetaTrader 5 installation."
            )
            return

        activation_code = (
            self._activation_entry.get().strip()
        )

        if not activation_code:
            self._set_status(
                "Enter your Activation Code."
            )
            return

        try:
            self._application_shell.connect(
                activation_code=activation_code,
                option=self._options[index],
            )
        except Exception:
            self._show_primary_action(
                "connect"
            )

            self._set_status(
                "Unable to connect. Check the Activation Code "
                "and try again."
            )
            raise
        finally:
            self._activation_entry.delete(
                0,
                "end",
            )

        self._show_primary_action(
            "verify"
        )

        self._set_status(
            "Connected. Verify VPS status to continue."
        )

    def verify_vps(
        self,
    ) -> None:
        self._require_built()

        try:
            result = (
                self._application_shell.verify()
            )
        except Exception:
            self._show_primary_action(
                "verify"
            )

            self._set_status(
                "Unable to verify VPS status."
            )
            raise

        if result.status == "vps_online":
            self._show_primary_action(
                "finish"
            )

            self._set_status(
                "TODOBA VPS is online. Ready to finish."
            )
            return

        self._show_primary_action(
            "verify"
        )

        self._set_status(
            "TODOBA VPS is not online yet. "
            "Complete VPS setup and verify again."
        )

    def finish(
        self,
    ) -> None:
        self._require_built()

        try:
            self._application_shell.finish()
        except RuntimeError:
            self._show_primary_action(
                "verify"
            )

            self._set_status(
                "VPS verification is required before Finish."
            )
            return

        self._close_window()

    def _close_window(
        self,
    ) -> None:
        self._require_built()

        root = self._root

        root.quit()
        root.destroy()

    def _show_primary_action(
        self,
        action: str,
    ) -> None:
        buttons = {
            "detect": self._detect_button,
            "connect": self._connect_button,
            "verify": self._verify_button,
            "finish": self._finish_button,
        }

        if action not in buttons:
            raise ValueError(
                "Unsupported VPS Connect primary action."
            )

        for button in buttons.values():
            button.pack_forget()
            button.configure(
                state="disabled",
            )

        selected = buttons[action]
        selected.configure(
            state="normal",
        )
        selected.pack(
            side=(
                "right"
                if action == "finish"
                else "left"
            ),
        )

    def _set_status(
        self,
        text: str,
    ) -> None:
        self._status_label.configure(
            text=text,
        )

    def _require_built(
        self,
    ) -> None:
        if self._root is None:
            raise RuntimeError(
                "VPS Connect window is not built."
            )

    @staticmethod
    def _option_label(
        option: Any,
    ) -> str:
        installation_path = getattr(
            option,
            "installation_path",
            None,
        )

        if installation_path is None:
            return "MetaTrader 5"

        return str(
            installation_path
        )