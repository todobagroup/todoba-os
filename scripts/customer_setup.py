"""
TODOBA production Windows Customer Setup entrypoint.

Customer-visible bootstrap flow:

    Welcome to TODOBA Trading
        -> generate customer-side PKCE material
        -> expose only code_challenge_s256
        -> receive one-time authorization_code
        -> CustomerSetupBootstrapAcquisition.launch()
        -> existing Coordinator
        -> existing Launcher
        -> existing MT5 discovery/install GUI

Security boundaries:
- the PKCE code_verifier remains private to
  CustomerSetupBootstrapAcquisition
- this entrypoint never reads or persists the verifier
- authorization_code exists only in GUI memory long enough
  to hand it to the acquisition owner
- no customer, deployment, payment, activation, or
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


WINDOW_TITLE = "TODOBA Trading AI Setup"
WELCOME_HEADLINE = "Welcome to TODOBA Trading"

_WINDOW_WIDTH = 640
_WINDOW_HEIGHT = 440

_BOOTSTRAP_INSTRUCTIONS = (
    "To securely start TODOBA Setup, copy the Setup Challenge "
    "below and provide it to TODOBA support. "
    "Then enter the one-time Authorization Code you receive."
)

_GENERIC_LAUNCH_ERROR = (
    "TODOBA Setup could not continue. "
    "Please verify the Authorization Code and try again."
)

_GENERIC_STARTUP_ERROR = (
    "TODOBA Setup could not start. "
    "Please contact TODOBA support."
)


class CustomerSetupBootstrapWindow:
    """
    Minimal pre-bootstrap customer window.

    Only the public PKCE challenge is displayed.
    """

    __slots__ = (
        "_acquisition",
        "_root",
        "_authorization_code_var",
        "_status_var",
        "_continue_button",
    )

    def __init__(
        self,
        *,
        acquisition: CustomerSetupBootstrapAcquisition,
    ) -> None:
        if not isinstance(
            acquisition,
            CustomerSetupBootstrapAcquisition,
        ):
            raise TypeError(
                "acquisition must be "
                "CustomerSetupBootstrapAcquisition."
            )

        self._acquisition = (
            acquisition
        )

        self._root = None
        self._authorization_code_var = None
        self._status_var = None
        self._continue_button = None

    def build_window(
        self,
    ):
        if self._root is not None:
            raise RuntimeError(
                "Bootstrap window is already built."
            )

        root = tk.Tk()

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
            padx=28,
            pady=24,
        )

        self._root = root

        headline = tk.Label(
            root,
            text=WELCOME_HEADLINE,
            font=(
                "Segoe UI",
                20,
                "bold",
            ),
        )

        headline.pack(
            pady=(
                0,
                14,
            ),
        )

        instructions = tk.Label(
            root,
            text=_BOOTSTRAP_INSTRUCTIONS,
            font=(
                "Segoe UI",
                10,
            ),
            justify="left",
            wraplength=570,
        )

        instructions.pack(
            anchor="w",
            pady=(
                0,
                16,
            ),
        )

        challenge_label = tk.Label(
            root,
            text="Setup Challenge",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
        )

        challenge_label.pack(
            anchor="w",
        )

        challenge_var = tk.StringVar(
            master=root,
            value=(
                self._acquisition
                .code_challenge_s256
            ),
        )

        challenge_entry = tk.Entry(
            root,
            textvariable=challenge_var,
            state="readonly",
            font=(
                "Consolas",
                10,
            ),
            width=72,
        )

        challenge_entry.pack(
            fill="x",
            pady=(
                5,
                8,
            ),
        )

        copy_button = tk.Button(
            root,
            text="Copy Challenge",
            command=self._copy_challenge,
            width=18,
        )

        copy_button.pack(
            anchor="w",
            pady=(
                0,
                18,
            ),
        )

        authorization_label = tk.Label(
            root,
            text="Authorization Code",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
        )

        authorization_label.pack(
            anchor="w",
        )

        self._authorization_code_var = (
            tk.StringVar(
                master=root,
                value="",
            )
        )

        authorization_entry = tk.Entry(
            root,
            textvariable=(
                self._authorization_code_var
            ),
            font=(
                "Consolas",
                10,
            ),
            width=72,
        )

        authorization_entry.pack(
            fill="x",
            pady=(
                5,
                10,
            ),
        )

        authorization_entry.focus_set()

        self._status_var = (
            tk.StringVar(
                master=root,
                value=(
                    "Your private verification key "
                    "never leaves this Setup."
                ),
            )
        )

        status_label = tk.Label(
            root,
            textvariable=(
                self._status_var
            ),
            font=(
                "Segoe UI",
                9,
            ),
            justify="left",
            wraplength=570,
        )

        status_label.pack(
            anchor="w",
            pady=(
                0,
                16,
            ),
        )

        self._continue_button = (
            tk.Button(
                root,
                text="Continue",
                command=(
                    self._submit_authorization_code
                ),
                width=18,
                default="active",
            )
        )

        self._continue_button.pack(
            anchor="e",
        )

        root.bind(
            "<Return>",
            lambda _event: (
                self._submit_authorization_code()
            ),
        )

        return root

    def run(
        self,
    ) -> None:
        root = self.build_window()

        root.mainloop()

    def _copy_challenge(
        self,
    ) -> None:
        root = self._require_root()

        root.clipboard_clear()

        root.clipboard_append(
            self._acquisition
            .code_challenge_s256
        )

        root.update()

        status = self._require_status_var()

        status.set(
            "Setup Challenge copied."
        )

    def _submit_authorization_code(
        self,
    ) -> None:
        root = self._require_root()

        authorization_var = (
            self._require_authorization_code_var()
        )

        status = self._require_status_var()

        button = (
            self._require_continue_button()
        )

        authorization_code = (
            authorization_var
            .get()
            .strip()
        )

        if not authorization_code:
            status.set(
                "Enter the Authorization Code "
                "to continue."
            )

            return

        # Remove the short-lived plaintext code from the
        # visible widget before crossing the bootstrap boundary.
        authorization_var.set(
            ""
        )

        button.configure(
            state=tk.DISABLED
        )

        status.set(
            "Connecting securely to TODOBA..."
        )

        root.update_idletasks()

        root.withdraw()

        try:
            self._acquisition.launch(
                authorization_code=(
                    authorization_code
                ),
            )
        except Exception:
            root.deiconify()

            button.configure(
                state=tk.NORMAL
            )

            status.set(
                _GENERIC_LAUNCH_ERROR
            )

            messagebox.showerror(
                WINDOW_TITLE,
                _GENERIC_LAUNCH_ERROR,
                parent=root,
            )

            return

        root.destroy()

    def _require_root(
        self,
    ):
        if self._root is None:
            raise RuntimeError(
                "Bootstrap window is not built."
            )

        return self._root

    def _require_authorization_code_var(
        self,
    ):
        if (
            self._authorization_code_var
            is None
        ):
            raise RuntimeError(
                "Authorization Code input "
                "is not built."
            )

        return self._authorization_code_var

    def _require_status_var(
        self,
    ):
        if self._status_var is None:
            raise RuntimeError(
                "Bootstrap status is not built."
            )

        return self._status_var

    def _require_continue_button(
        self,
    ):
        if self._continue_button is None:
            raise RuntimeError(
                "Continue button is not built."
            )

        return self._continue_button


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

    window = (
        CustomerSetupBootstrapWindow(
            acquisition=acquisition,
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
