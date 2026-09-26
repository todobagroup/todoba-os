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
import sys
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

_WINDOW_WIDTH = 922
_WINDOW_HEIGHT = 542


_GENERIC_STARTUP_ERROR = (
    "TODOBA Setup could not start. "
    "Please contact TODOBA support."
)


def _runtime_resource_path(
    *parts: str,
) -> Path:
    """
    Resolve a packaged runtime resource.

    Source execution resolves from the repository root.
    PyInstaller execution resolves from the frozen bundle root.
    """

    if getattr(
        sys,
        "frozen",
        False,
    ):
        bundle_root = getattr(
            sys,
            "_MEIPASS",
            None,
        )

        if not isinstance(
            bundle_root,
            str,
        ) or not bundle_root.strip():
            raise RuntimeError(
                "TODOBA Setup packaged resource root "
                "is unavailable."
            )

        return (
            Path(bundle_root)
            .resolve()
            .joinpath(
                *parts
            )
        )

    return (
        Path(__file__)
        .resolve()
        .parents[1]
        .joinpath(
            *parts
        )
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
    ):
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

        root.configure(
            bg="#FFFFFF"
        )

        canvas = tk.Canvas(
            root,
            width=_WINDOW_WIDTH,
            height=_WINDOW_HEIGHT,
            highlightthickness=0,
            bd=0,
            bg="#FFFFFF",
        )
        canvas.pack(
            fill="both",
            expand=False,
        )

        artwork_path = (
            _runtime_resource_path(
                "assets",
                "customer_setup_runtime_final.png",
            )
        )

        icon_path = (
            _runtime_resource_path(
                "assets",
                "TODOBA_Trading.ico",
            )
        )

        if not artwork_path.is_file():
            raise RuntimeError(
                "TODOBA Setup runtime artwork is unavailable."
            )

        if not icon_path.is_file():
            raise RuntimeError(
                "TODOBA Setup icon is unavailable."
            )

        root.iconbitmap(
            str(
                icon_path
            )
        )

        artwork_image = tk.PhotoImage(
            file=str(
                artwork_path
            )
        )

        if (
            artwork_image.width()
            != _WINDOW_WIDTH
            or artwork_image.height()
            != _WINDOW_HEIGHT
        ):
            raise RuntimeError(
                "TODOBA Setup runtime artwork dimensions "
                "do not match the locked window."
            )

        # Pixel-perfect runtime:
        # no zoom, no subsample, no runtime crop.
        root._todoba_setup_artwork = (
            artwork_image
        )

        canvas.create_image(
            0,
            0,
            anchor="nw",
            image=artwork_image,
        )

        # The approved artwork owns all non-interactive typography.
        # Only the input field and Start Setup button are replaced
        # by real widgets.

        canvas.create_rectangle(
            36,
            244,
            410,
            280,
            fill="#FFFFFF",
            outline="#FFFFFF",
        )

        canvas.create_rectangle(
            36,
            285,
            240,
            327,
            fill="#FFFFFF",
            outline="#FFFFFF",
        )

        activation_code_var = tk.StringVar(
            master=root,
            value="",
        )

        self._activation_code_var = (
            activation_code_var
        )

        customer_instruction = (
            "Enter your Activation Code to begin."
        )
        activation_label_text = (
            "Activation Code"
        )

        # These locked customer-visible strings are rendered by the
        # approved 1:1 artwork. Keep them explicit in source so the
        # Single-Code customer contract remains auditable.
        _ = (
            customer_instruction,
            activation_label_text,
        )

        entry_frame = tk.Frame(
            canvas,
            bg="#AFC2D8",
            padx=2,
            pady=2,
        )

        entry_frame.place(
            x=38,
            y=247,
            width=370,
            height=31,
        )

        activation_entry = tk.Entry(
            entry_frame,
            textvariable=activation_code_var,
            font=(
                "Segoe UI",
                12,
            ),
            relief="flat",
            bd=0,
            bg="#FFFFFF",
            fg="#172033",
            insertbackground="#079A82",
        )

        activation_entry.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
            ipady=10,
        )

        # The visible Start Setup artwork remains pixel-authored by
        # the locked PNG. This real Tk button owns runtime enabled /
        # disabled state for the existing submit boundary.
        start_button = tk.Button(
            canvas,
            text="Start Setup",
            command=(
                self._submit_activation_code
            ),
            font=(
                "Segoe UI",
                11,
                "bold",
            ),
            fg="#FFFFFF",
            bg="#0A9B83",
            activebackground="#087D6C",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
        )

        self._start_button = (
            start_button
        )

        start_button.place(
            x=38,
            y=287,
            width=199,
            height=37,
        )

        status_var = tk.StringVar(
            master=root,
            value="",
        )

        self._status_var = (
            status_var
        )

        status_label = tk.Label(
            canvas,
            textvariable=status_var,
            font=(
                "Segoe UI",
                9,
            ),
            fg="#475467",
            bg="#FFFFFF",
            anchor="w",
            justify="left",
        )

        status_label.place(
            x=246,
            y=292,
            width=180,
            height=28,
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
