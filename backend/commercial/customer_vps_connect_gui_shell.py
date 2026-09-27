"""
Thin standalone presentation shell for TODOBA VPS Connect.
"""

from pathlib import Path
import sys
from typing import Any

import tkinter as tk
from tkinter import ttk

from backend.commercial.customer_vps_connect_application_shell import (
    CustomerVPSConnectApplicationShell,
)


WINDOW_TITLE = "TODOBA VPS Setup"

_WINDOW_WIDTH = 922
_WINDOW_HEIGHT = 542

_ARTWORK_FILENAME = (
    "customer_vps_setup_runtime_final.png"
)

_ICON_FILENAME = "TODOBA_Trading.ico"


def _runtime_resource_path(
    *parts: str,
) -> Path:
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

        if (
            not isinstance(
                bundle_root,
                str,
            )
            or not bundle_root
        ):
            raise RuntimeError(
                "Frozen VPS Setup resource root "
                "is unavailable."
            )

        root = Path(bundle_root)
    else:
        root = (
            Path(__file__)
            .resolve()
            .parents[2]
        )

    return root.joinpath(
        *parts
    )


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
            f"{_WINDOW_WIDTH}x{_WINDOW_HEIGHT}"
        )

        root.resizable(
            False,
            False,
        )

        artwork_path = (
            _runtime_resource_path(
                "assets",
                _ARTWORK_FILENAME,
            )
        )

        icon_path = (
            _runtime_resource_path(
                "assets",
                _ICON_FILENAME,
            )
        )

        if not artwork_path.is_file():
            raise RuntimeError(
                "TODOBA VPS Setup runtime artwork "
                "is unavailable."
            )

        if not icon_path.is_file():
            raise RuntimeError(
                "TODOBA VPS Setup icon "
                "is unavailable."
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
                "TODOBA VPS Setup runtime artwork "
                "dimensions do not match "
                "the locked window."
            )

        root._todoba_vps_artwork = (
            artwork_image
        )

        canvas = tk.Canvas(
            root,
            width=_WINDOW_WIDTH,
            height=_WINDOW_HEIGHT,
            highlightthickness=0,
            bd=0,
        )

        canvas.pack(
            fill="both",
            expand=False,
        )

        canvas.create_image(
            0,
            0,
            anchor="nw",
            image=artwork_image,
        )

        self._root = root

        # Activation Code:
        # preserve the approved artwork border/icon,
        # overlay only the real secret input.
        activation_host = tk.Frame(
            canvas,
            bg="#FFFFFF",
            bd=0,
        )

        activation_host.place(
            x=192,
            y=309,
            width=565,
            height=27,
        )

        self._activation_entry = ttk.Entry(
            activation_host,
            show="*",
        )

        self._activation_entry.pack(
            fill="both",
            expand=True,
        )

        # Runtime-owned presentation regions.
        #
        # The approved artwork remains the visual authority.
        # Canvas adapters provide interaction without placing
        # native opaque widgets over the designed surfaces.

        status_text_id = canvas.create_text(
            461,
            399,
            text="",
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
            fill="#102A72",
            anchor="center",
            width=400,
        )

        class _CanvasStatusLabel:
            def __init__(
                self,
                owner_canvas,
                item_id,
            ):
                self._canvas = owner_canvas
                self._item_id = item_id

            def config(
                self,
                **kwargs,
            ):
                if "text" in kwargs:
                    self._canvas.itemconfigure(
                        self._item_id,
                        text=kwargs["text"],
                    )

            configure = config

        self._status_label = _CanvasStatusLabel(
            canvas,
            status_text_id,
        )

        # Preserve the approved MT5 card/title from the artwork.
        # Overlay only the live customer installation selector.
        self._mt5_selector = ttk.Combobox(
            canvas,
            values=(),
            state="readonly",
        )

        self._mt5_selector.place(
            x=266,
            y=446,
            width=456,
            height=23,
        )

        action_text_id = canvas.create_text(
            461,
            359,
            text="",
            font=(
                "Arial",
                15,
                "bold",
            ),
            fill="#FFFFFF",
            anchor="center",
        )

        class _CanvasActionButton:
            def __init__(
                self,
                *,
                owner_canvas,
                item_id,
                label,
                command,
            ):
                self._canvas = owner_canvas
                self._item_id = item_id
                self._label = label
                self._command = command
                self.state = "disabled"
                self.visible = False

            def configure(
                self,
                **kwargs,
            ):
                if "state" in kwargs:
                    self.state = kwargs["state"]

            config = configure

            def cget(
                self,
                key,
            ):
                if key == "state":
                    return self.state

                if key == "text":
                    return self._label

                raise KeyError(
                    key
                )

            def pack_forget(
                self,
            ):
                self.visible = False

            def pack(
                self,
                *args,
                **kwargs,
            ):
                self.visible = True
                self._canvas.itemconfigure(
                    self._item_id,
                    text=self._label,
                )

            def invoke(
                self,
            ):
                if (
                    self.visible
                    and self.state == "normal"
                ):
                    self._command()

        self._detect_button = _CanvasActionButton(
            owner_canvas=canvas,
            item_id=action_text_id,
            label="Detect",
            command=self.detect_mt5,
        )

        self._connect_button = _CanvasActionButton(
            owner_canvas=canvas,
            item_id=action_text_id,
            label="Connect",
            command=self.connect_selected,
        )

        self._verify_button = _CanvasActionButton(
            owner_canvas=canvas,
            item_id=action_text_id,
            label="Verify",
            command=self.verify_vps,
        )

        self._finish_button = _CanvasActionButton(
            owner_canvas=canvas,
            item_id=action_text_id,
            label="Finish",
            command=self.finish,
        )

        def _invoke_primary_action(
            _event=None,
        ):
            buttons = (
                self._detect_button,
                self._connect_button,
                self._verify_button,
                self._finish_button,
            )

            for button in buttons:
                if (
                    button.visible
                    and button.state == "normal"
                ):
                    button.invoke()
                    return

        canvas.tag_bind(
            action_text_id,
            "<Button-1>",
            _invoke_primary_action,
        )

        # Make the full designed gradient surface clickable,
        # not just its text.
        action_hitbox = canvas.create_rectangle(
            382,
            341,
            540,
            376,
            fill="",
            outline="",
        )

        canvas.tag_bind(
            action_hitbox,
            "<Button-1>",
            _invoke_primary_action,
        )

        self._show_primary_action(
            "detect"
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

        if result.status == "runtime_ready":
            self._set_status(
                "TODOBA is ready. "
                "Complete the VPS migration in MetaTrader 5. "
                "TODOBA will verify automatically."
            )

            self._start_migration_observation()
            return

        self._set_status(
            "TODOBA VPS is not ready yet. "
            "Keep MetaTrader 5 open and complete the VPS migration "
            "if needed, then select Verify."
        )

    def _start_migration_observation(
        self,
    ) -> None:
        self._require_built()

        try:
            self._application_shell.begin_migration_observation()
            self._observe_migration()
        except Exception:
            self._show_primary_action(
                "verify"
            )

            self._set_status(
                "TODOBA could not complete the automatic VPS check. "
                "Select Verify to try again."
            )
            raise

    def _observe_migration(
        self,
    ) -> None:
        self._require_built()

        try:
            result = (
                self._application_shell.observe_migration()
            )
        except Exception:
            self._show_primary_action(
                "verify"
            )

            self._set_status(
                "TODOBA could not complete the automatic VPS check. "
                "Select Verify to try again."
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

        if result.status == "observation_exhausted":
            self._show_primary_action(
                "verify"
            )

            self._set_status(
                "TODOBA VPS is not ready yet. "
                "Keep MetaTrader 5 open and complete the VPS migration "
                "if needed, then select Verify."
            )
            return

        if result.status != "observation_pending":
            self._show_primary_action(
                "verify"
            )

            self._set_status(
                "Automatic VPS verification stopped."
            )

            raise RuntimeError(
                "Unsupported VPS migration observation status."
            )

        retry_after_ms = getattr(
            result,
            "retry_after_ms",
            None,
        )

        if (
            not isinstance(
                retry_after_ms,
                int,
            )
            or isinstance(
                retry_after_ms,
                bool,
            )
            or retry_after_ms < 1
        ):
            self._show_primary_action(
                "verify"
            )

            raise RuntimeError(
                "Invalid VPS migration retry interval."
            )

        self._show_primary_action(
            "verify"
        )

        self._set_status(
            "Waiting for MetaTrader VPS. "
            "TODOBA will continue automatically."
        )

        self._root.after(
            retry_after_ms,
            self._observe_migration,
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
