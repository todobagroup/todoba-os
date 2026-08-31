"""
TODOBA Windows Customer Setup Packaging Smoke

Frozen-runtime proof only.

This script proves that a packaged Windows executable can:
- start the Python frozen runtime
- load Tcl/Tk
- load the MetaTrader5 native package
- import and construct CustomerSetupLauncher

It does not:
- contact TODOBA Cloud
- exchange a setup launch credential
- provision a customer
- download or install EX5
- open the customer Setup GUI
- claim runtime or trading readiness
"""

from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk

import MetaTrader5 as mt5

from backend.commercial.customer_setup_bootstrap_input import (
    CustomerSetupBootstrapInput,
)
from backend.commercial.customer_setup_launcher import (
    CustomerSetupLauncher,
)


_SMOKE_BASE_URL = (
    "https://packaging-proof.invalid"
)

_SMOKE_LAUNCH_CREDENTIAL = (
    "packaging-proof-not-a-real-credential"
)


def run_packaging_smoke(
) -> tuple[str, ...]:
    """
    Run local dependency-load proof without network or GUI flow.
    """

    # Tcl() proves the Tcl/Tk runtime can actually initialize
    # without opening a customer-facing window.
    tcl = tk.Tcl()

    tcl_version = str(
        tcl.eval(
            "info patchlevel"
        )
    )

    bootstrap_input = (
        CustomerSetupBootstrapInput(
            setup_base_url=(
                _SMOKE_BASE_URL
            ),
            setup_launch_credential=(
                _SMOKE_LAUNCH_CREDENTIAL
            ),
        )
    )

    launcher = CustomerSetupLauncher(
        bootstrap_input=bootstrap_input,
        mt5_module=mt5,
        roaming_appdata_path=(
            Path.home()
            / "AppData"
            / "Roaming"
        ),
    )

    if not isinstance(
        launcher,
        CustomerSetupLauncher,
    ):
        raise RuntimeError(
            "Customer Setup launcher construction failed."
        )

    frozen = bool(
        getattr(
            sys,
            "frozen",
            False,
        )
    )

    return (
        "TODOBA_PACKAGING_SMOKE=GREEN",
        f"FROZEN={int(frozen)}",
        f"TCL={tcl_version}",
        f"TK={tk.TkVersion}",
        (
            "METATRADER5="
            f"{getattr(mt5, '__version__', 'UNKNOWN')}"
        ),
        "CUSTOMER_SETUP_LAUNCHER=READY",
    )


def main(
) -> int:
    for line in run_packaging_smoke():
        print(
            line,
            flush=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )