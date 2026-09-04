"""
TODOBA Customer Setup GUI Shell

Customer-facing presentation layer for TODOBA Setup.

The shell:
- presents discovered MetaTrader 5 installations
- lets the customer select one exact installation
- delegates setup work to CustomerSetupApplicationController
- presents build-pending or installed outcomes
- never polls automatically

The shell owns presentation only. Production dependency
composition is intentionally outside this module.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from backend.commercial.customer_setup_application_controller import (
    CustomerSetupApplicationController,
    CustomerSetupApplicationResult,
    CustomerSetupInstallationOption,
)


WINDOW_TITLE = (
    'TODOBA Trading AI Setup'
)
WELCOME_HEADLINE = (
    'Welcome to TODOBA Trading'
)
WELCOME_SUBTITLE = (
    'Set up TODOBA Trading AI for your MetaTrader 5 account.'
)

_DISCOVERY_PROMPT = (
    'Select the MetaTrader 5 installation that is signed in to the account you want to use with TODOBA.'
)
_DISCOVERING_MESSAGE = (
    'Searching for MetaTrader 5 installations...'
)
_NO_INSTALLATION_MESSAGE = (
    'No supported MetaTrader 5 installation was found. Open MetaTrader 5, sign in to your account, then select Refresh.'
)
_READY_TO_INSTALL_MESSAGE = (
    'Select a MetaTrader 5 installation, then select Install.'
)
_PREPARING_MESSAGE = (
    'Preparing TODOBA Trading AI for this MetaTrader 5 account. When ready, select Continue.'
)
_INSTALLED_MESSAGE = (
    'TODOBA Trading AI was installed successfully.'
)
_GENERIC_ERROR_MESSAGE = (
    'Setup could not complete this step. Please try again.'
)
_NO_SELECTION_MESSAGE = (
    'Select a MetaTrader 5 installation to continue.'
)


class CustomerSetupGuiShell:
    """
    Thin tkinter presentation shell for TODOBA Setup.
    """

    def __init__(
        self,
        *,
        controller: CustomerSetupApplicationController,
        roaming_appdata_path: Path,
    ) -> None:
        if not isinstance(
            controller,
            CustomerSetupApplicationController,
        ):
            raise TypeError(
                "controller must be "
                "CustomerSetupApplicationController."
            )

        if not isinstance(
            roaming_appdata_path,
            Path,
        ):
            raise TypeError(
                "roaming_appdata_path must be Path."
            )

        self._controller = controller
        self._roaming_appdata_path = (
            roaming_appdata_path
        )

        self._options: tuple[
            CustomerSetupInstallationOption,
            ...,
        ] = ()

        self._root = None
        self._installation_list = None
        self._status_var = None
        self._account_var = None
        self._refresh_button = None
        self._install_button = None
        self._finish_button = None

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
                "TODOBA Setup window is already built."
            )

        root = tk.Tk()
        root.title(
            WINDOW_TITLE
        )
        root.geometry(
            "700x500"
        )
        root.resizable(
            False,
            False,
        )

        container = ttk.Frame(
            root,
            padding=28,
        )
        container.pack(
            fill="both",
            expand=True,
        )

        ttk.Label(
            container,
            text=WELCOME_HEADLINE,
            font=(
                "Segoe UI",
                20,
                "bold",
            ),
        ).pack(
            anchor="w",
        )

        ttk.Label(
            container,
            text=WELCOME_SUBTITLE,
            font=(
                "Segoe UI",
                10,
            ),
        ).pack(
            anchor="w",
            pady=(
                4,
                22,
            ),
        )

        ttk.Label(
            container,
            text=_DISCOVERY_PROMPT,
            wraplength=620,
            justify="left",
        ).pack(
            anchor="w",
            pady=(
                0,
                8,
            ),
        )

        self._installation_list = (
            tk.Listbox(
                container,
                height=8,
                exportselection=False,
                font=(
                    "Segoe UI",
                    10,
                ),
            )
        )
        self._installation_list.pack(
            fill="x",
            pady=(
                0,
                12,
            ),
        )
        self._installation_list.bind(
            "<<ListboxSelect>>",
            self._on_selection_changed,
        )

        self._status_var = tk.StringVar(
            value=_DISCOVERING_MESSAGE
        )
        ttk.Label(
            container,
            textvariable=(
                self._status_var
            ),
            wraplength=620,
            justify="left",
        ).pack(
            anchor="w",
            pady=(
                4,
                4,
            ),
        )

        self._account_var = tk.StringVar(
            value=""
        )
        ttk.Label(
            container,
            textvariable=(
                self._account_var
            ),
            wraplength=620,
            justify="left",
        ).pack(
            anchor="w",
            pady=(
                0,
                18,
            ),
        )

        button_row = ttk.Frame(
            container,
        )
        button_row.pack(
            fill="x",
        )

        self._refresh_button = ttk.Button(
            button_row,
            text='Refresh',
            command=(
                self.refresh_installations
            ),
        )
        self._refresh_button.pack(
            side="left",
        )

        self._install_button = ttk.Button(
            button_row,
            text="Install",
            command=(
                self.install_selected
            ),
            state="disabled",
        )
        self._install_button.pack(
            side="right",
            padx=(
                8,
                0,
            ),
        )

        self._finish_button = ttk.Button(
            button_row,
            text="Finish",
            command=self._finish_setup,
            state="disabled",
        )
        self._finish_button.pack(
            side="right",
        )

        self._root = root

        root.protocol(
            "WM_DELETE_WINDOW",
            self._finish_setup,
        )

        self.refresh_installations()

        return root

    def refresh_installations(
        self,
    ) -> None:
        self._require_built()

        self._status_var.set(
            _DISCOVERING_MESSAGE
        )
        self._account_var.set(
            ""
        )

        self._install_button.configure(
            state="disabled",
            text="Install",
        )

        try:
            options = (
                self._controller
                .discover_standard_installations(
                    roaming_appdata_path=(
                        self._roaming_appdata_path
                    ),
                )
            )
        except Exception:
            self._options = ()
            self._replace_installation_list(
                ()
            )
            self._status_var.set(
                _GENERIC_ERROR_MESSAGE
            )
            return

        if not isinstance(
            options,
            tuple,
        ):
            self._options = ()
            self._replace_installation_list(
                ()
            )
            self._status_var.set(
                _GENERIC_ERROR_MESSAGE
            )
            return

        for option in options:
            if not isinstance(
                option,
                CustomerSetupInstallationOption,
            ):
                self._options = ()
                self._replace_installation_list(
                    ()
                )
                self._status_var.set(
                    _GENERIC_ERROR_MESSAGE
                )
                return

        self._options = options
        self._replace_installation_list(
            options
        )

        if not options:
            self._status_var.set(
                _NO_INSTALLATION_MESSAGE
            )
            return

        self._status_var.set(
            _READY_TO_INSTALL_MESSAGE
        )

    def install_selected(
        self,
    ) -> None:
        self._require_built()

        selected = (
            self._installation_list
            .curselection()
        )

        if len(
            selected
        ) != 1:
            self._status_var.set(
                _NO_SELECTION_MESSAGE
            )
            return

        index = selected[0]

        if (
            not isinstance(
                index,
                int,
            )
            or index < 0
            or index >= len(
                self._options
            )
        ):
            self._status_var.set(
                _GENERIC_ERROR_MESSAGE
            )
            return

        option = self._options[
            index
        ]

        self._install_button.configure(
            state="disabled",
        )
        self._refresh_button.configure(
            state="disabled",
        )
        self._status_var.set(
            'Setting up TODOBA Trading AI...'
        )
        self._account_var.set(
            ""
        )

        try:
            result = (
                self._controller.run_selected(
                    option=option
                )
            )
        except Exception:
            self._status_var.set(
                _GENERIC_ERROR_MESSAGE
            )
            self._refresh_button.configure(
                state="normal",
            )
            self._install_button.configure(
                state="normal",
                text="Retry",
            )
            return

        if not isinstance(
            result,
            CustomerSetupApplicationResult,
        ):
            self._status_var.set(
                _GENERIC_ERROR_MESSAGE
            )
            self._refresh_button.configure(
                state="normal",
            )
            self._install_button.configure(
                state="normal",
                text="Retry",
            )
            return

        self._show_verified_account(
            result
        )

        if result.status == "build_pending":
            self._status_var.set(
                _PREPARING_MESSAGE
            )
            self._refresh_button.configure(
                state="normal",
            )
            self._install_button.configure(
                state="normal",
                text='Continue',
            )
            return

        if result.status != "installed":
            self._status_var.set(
                _GENERIC_ERROR_MESSAGE
            )
            self._refresh_button.configure(
                state="normal",
            )
            self._install_button.configure(
                state="normal",
                text="Retry",
            )
            return

        self._status_var.set(
            _INSTALLED_MESSAGE
        )
        self._installation_list.configure(
            state="disabled",
        )
        self._refresh_button.configure(
            state="disabled",
        )
        self._install_button.configure(
            state="disabled",
            text="Install",
        )
        self._finish_button.configure(
            state="normal",
        )

    def _finish_setup(
        self,
    ) -> None:
        self._require_built()

        self._root.quit()
        self._root.destroy()

    def _on_selection_changed(
        self,
        _event=None,
    ) -> None:
        self._require_built()

        selected = (
            self._installation_list
            .curselection()
        )

        if (
            len(
                selected
            ) == 1
            and self._finish_button.cget(
                "state"
            )
            != "normal"
        ):
            self._install_button.configure(
                state="normal",
            )
            return

        self._install_button.configure(
            state="disabled",
        )

    def _replace_installation_list(
        self,
        options: tuple[
            CustomerSetupInstallationOption,
            ...,
        ],
    ) -> None:
        self._installation_list.configure(
            state="normal",
        )
        self._installation_list.delete(
            0,
            tk.END,
        )

        for option in options:
            label = (
                "MetaTrader 5 — "
                f"{option.installation_path}"
            )

            if option.portable:
                label = (
                    f"{label} (Portable)"
                )

            self._installation_list.insert(
                tk.END,
                label,
            )

    def _show_verified_account(
        self,
        result: CustomerSetupApplicationResult,
    ) -> None:
        self._account_var.set(
            'Verified MT5 account (HEDGING)\n'
            f"{result.server} / "
            f"{result.login}"
        )

    def _require_built(
        self,
    ) -> None:
        if (
            self._root is None
            or self._installation_list
            is None
            or self._status_var is None
            or self._account_var is None
            or self._refresh_button is None
            or self._install_button is None
            or self._finish_button is None
        ):
            raise RuntimeError(
                "TODOBA Setup window is not built."
            )
