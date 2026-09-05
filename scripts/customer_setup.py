"""
TODOBA production Windows Customer Setup entrypoint.

Customer-visible start flow:

    Welcome to TODOBA Trading
        -> enter one Activation Code
        -> Start Setup
        -> hidden activation/bootstrap bridge
        -> existing Coordinator
        -> existing Launcher
        -> existing MT5 discovery/install GUI

Security boundaries:
- customer-visible Setup does not expose PKCE challenge material
- internal bootstrap authorization codes are never customer-visible
- the private PKCE verifier remains inside
  CustomerSetupBootstrapAcquisition
- no customer, deployment, payment, entitlement, or
  launch-credential authority is owned here
"""

from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import MetaTrader5 as mt5

from backend.config import (
    TODOBA_CLOUD_BASE_URL,
)
from backend.commercial.customer_setup_bootstrap_acquisition import (
    CustomerSetupBootstrapAcquisition,
)
from backend.commercial.customer_setup_access_code_bootstrap_bridge import (
    CustomerSetupAccessCodeBootstrapBridge,
)
from backend.commercial.customer_setup_access_code_http_client import (
    CustomerSetupAccessCodeHttpClient,
)


WINDOW_TITLE = "TODOBA Trading AI Setup"
WELCOME_HEADLINE = "Welcome to TODOBA Trading"

_WINDOW_WIDTH = 640
_WINDOW_HEIGHT = 440

_GENERIC_STARTUP_ERROR = (
    "TODOBA Setup could not start. "
    "Please contact TODOBA support."
)


class CustomerSetupBootstrapWindow:
    """
    Customer-facing TODOBA Setup start window.

    The customer enters one Activation Code.

    PKCE challenge material and the internal bootstrap authorization
    ceremony remain hidden behind CustomerSetupAccessCodeBootstrapBridge.
    """

    __slots__ = (
        "_bridge",
        "_root",
        "_activation_code_var",
        "_status_var",
        "_start_button",
    )

    def __init__(
        self,
        *,
        bridge: CustomerSetupAccessCodeBootstrapBridge,
    ) -> None:
        if not isinstance(
            bridge,
            CustomerSetupAccessCodeBootstrapBridge,
        ):
            raise TypeError(
                "bridge must be "
                "CustomerSetupAccessCodeBootstrapBridge."
            )

        self._bridge = bridge

        self._root = None
        self._activation_code_var = None
        self._status_var = None
        self._start_button = None

    def build_window(
            self,
        ) -> None:
            root = tk.Tk()

            self._root = root

            root.title(
                WINDOW_TITLE
            )

            root.geometry(
                f"{_WINDOW_WIDTH}x{_WINDOW_HEIGHT}"
            )

            root.resizable(
                False,
                False,
            )

            root.columnconfigure(
                0,
                weight=1,
            )

            content = tk.Frame(
                root,
                padx=42,
                pady=36,
            )

            content.grid(
                row=0,
                column=0,
                sticky="nsew",
            )

            content.columnconfigure(
                0,
                weight=1,
            )

            headline = tk.Label(
                content,
                text=WELCOME_HEADLINE,
                font=(
                    "Segoe UI",
                    20,
                    "bold",
                ),
            )

            headline.grid(
                row=0,
                column=0,
                sticky="w",
                pady=(
                    0,
                    18,
                ),
            )

            instructions = tk.Label(
                content,
                text=(
                    "Enter your Activation Code to begin."
                ),
                font=(
                    "Segoe UI",
                    11,
                ),
                anchor="w",
                justify="left",
            )

            instructions.grid(
                row=1,
                column=0,
                sticky="ew",
                pady=(
                    0,
                    24,
                ),
            )

            activation_label = tk.Label(
                content,
                text="Activation Code",
                font=(
                    "Segoe UI",
                    10,
                    "bold",
                ),
                anchor="w",
            )

            activation_label.grid(
                row=2,
                column=0,
                sticky="w",
                pady=(
                    0,
                    7,
                ),
            )

            activation_code_var = tk.StringVar(
                master=root,
                value="",
            )

            self._activation_code_var = (
                activation_code_var
            )

            activation_entry = tk.Entry(
                content,
                textvariable=(
                    activation_code_var
                ),
                font=(
                    "Segoe UI",
                    11,
                ),
            )

            activation_entry.grid(
                row=3,
                column=0,
                sticky="ew",
                pady=(
                    0,
                    22,
                ),
            )

            start_button = tk.Button(
                content,
                text="Start Setup",
                command=(
                    self._submit_activation_code
                ),
                width=18,
            )

            self._start_button = (
                start_button
            )

            start_button.grid(
                row=4,
                column=0,
                sticky="w",
            )

            status_var = tk.StringVar(
                master=root,
                value="",
            )

            self._status_var = (
                status_var
            )

            status_label = tk.Label(
                content,
                textvariable=status_var,
                font=(
                    "Segoe UI",
                    9,
                ),
                anchor="w",
                justify="left",
                wraplength=540,
            )

            status_label.grid(
                row=5,
                column=0,
                sticky="ew",
                pady=(
                    18,
                    0,
                ),
            )

            root.bind(
                "<Return>",
                lambda event: (
                    self._submit_activation_code()
                ),
            )

            activation_entry.focus_set()

            return root

    def run(
        self,
    ) -> None:
        root = (
            self.build_window()
        )

        root.mainloop()

    def _submit_activation_code(
        self,
    ) -> None:
        root = self._require_root()
        activation_code_var = (
            self._require_activation_code_var()
        )
        status = (
            self._require_status_var()
        )
        start_button = (
            self._require_start_button()
        )

        activation_code = (
            activation_code_var
            .get()
            .strip()
        )

        if not activation_code:
            status.set(
                "Enter your Activation Code "
                "to begin."
            )

            return

        # Remove the plaintext customer code from the visible
        # widget before crossing the hidden activation boundary.
        activation_code_var.set(
            ""
        )

        start_button.configure(
            state="disabled"
        )

        status.set(
            "Starting TODOBA Setup..."
        )

        root.update_idletasks()
        root.withdraw()

        try:
            self._bridge.launch(
                activation_code=(
                    activation_code
                ),
            )

        except Exception:
            root.deiconify()

            start_button.configure(
                state="normal"
            )

            status.set(
                "TODOBA Setup could not continue. "
                "Please verify your Activation Code "
                "and try again."
            )

            return

        root.destroy()

    def _require_root(
        self,
    ):
        if self._root is None:
            raise RuntimeError(
                "Customer Setup window "
                "is not built."
            )

        return self._root

    def _require_activation_code_var(
        self,
    ):
        if self._activation_code_var is None:
            raise RuntimeError(
                "Activation Code input "
                "is not built."
            )

        return self._activation_code_var

    def _require_status_var(
        self,
    ):
        if self._status_var is None:
            raise RuntimeError(
                "Status output is not built."
            )

        return self._status_var

    def _require_start_button(
        self,
    ):
        if self._start_button is None:
            raise RuntimeError(
                "Start Setup button "
                "is not built."
            )

        return self._start_button



def _resolve_roaming_appdata_path(
) -> Path:
    value = os.environ.get(
        "APPDATA"
    )

    if not isinstance(
        value,
        str,
    ):
        raise RuntimeError(
            "Windows APPDATA is not available."
        )

    normalized = value.strip()

    if not normalized:
        raise RuntimeError(
            "Windows APPDATA is not available."
        )

    return Path(
        normalized
    )


def run_production_customer_setup(
) -> None:
    acquisition = (
        CustomerSetupBootstrapAcquisition(
            setup_base_url=(
                TODOBA_CLOUD_BASE_URL
            ),
            mt5_module=mt5,
            roaming_appdata_path=(
                _resolve_roaming_appdata_path()
            ),
        )
    )

    access_code_client = (
        CustomerSetupAccessCodeHttpClient(
            setup_base_url=(
                TODOBA_CLOUD_BASE_URL
            ),
        )
    )

    bridge = (
        CustomerSetupAccessCodeBootstrapBridge(
            access_code_client=(
                access_code_client
            ),
            acquisition=(
                acquisition
            ),
        )
    )

    window = (
        CustomerSetupBootstrapWindow(
            bridge=bridge
        )
    )

    window.run()



def main(
) -> int:
    try:
        run_production_customer_setup()
    except Exception:
        try:
            messagebox.showerror(
                WINDOW_TITLE,
                _GENERIC_STARTUP_ERROR,
            )
        except Exception:
            pass

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
