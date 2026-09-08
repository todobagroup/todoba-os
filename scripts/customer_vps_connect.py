"""
Production Windows entrypoint for TODOBA VPS Connect.
"""

import os
from pathlib import Path
from tkinter import messagebox

import MetaTrader5 as mt5

from backend.config import (
    TODOBA_CLOUD_BASE_URL,
)

from backend.commercial.customer_vps_connect_launcher import (
    CustomerVPSConnectLauncher,
)


WINDOW_TITLE = "TODOBA VPS Connect"

_GENERIC_STARTUP_ERROR = (
    "TODOBA VPS Connect could not start. "
    "Please try again."
)


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


def run_production_customer_vps_connect(
) -> None:
    launcher = CustomerVPSConnectLauncher(
        cloud_base_url=TODOBA_CLOUD_BASE_URL,
        roaming_appdata_path=(
            _resolve_roaming_appdata_path()
        ),
        mt5_module=mt5,
    )

    launcher.run()


def main(
) -> int:
    try:
        run_production_customer_vps_connect()
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