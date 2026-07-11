"""
TODOBA Application Configuration

Loads runtime configuration from the repository .env file.

Secrets must never be committed to Git.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


def _read_int(
    name: str,
    default: int = 0,
) -> int:
    raw_value = os.getenv(
        name,
        str(default),
    ).strip()

    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(
            f"{name} must be a valid integer."
        ) from error


def _read_float(
    name: str,
    default: float,
) -> float:
    raw_value = os.getenv(
        name,
        str(default),
    ).strip()

    try:
        return float(raw_value)
    except ValueError as error:
        raise ValueError(
            f"{name} must be a valid number."
        ) from error


TELEGRAM_API_ID = _read_int(
    "TELEGRAM_API_ID"
)

TELEGRAM_API_HASH = os.getenv(
    "TELEGRAM_API_HASH",
    "",
).strip()

TELEGRAM_SESSION = os.getenv(
    "TELEGRAM_SESSION",
    "todoba",
).strip()

TELEGRAM_SIGNAL_GROUP = os.getenv(
    "TELEGRAM_SIGNAL_GROUP",
    "",
).strip()

TELEGRAM_SIGNAL_GROUP_ID = _read_int(
    "TELEGRAM_SIGNAL_GROUP_ID"
)

TELEGRAM_EXECUTION_MODE = os.getenv(
    "TELEGRAM_EXECUTION_MODE",
    "DRY_RUN",
).strip().upper()

MT5_BROKER_GOLD_SYMBOL = os.getenv(
    "MT5_BROKER_GOLD_SYMBOL",
    "GOLD.i#",
).strip()

MT5_MAX_SPREAD_POINTS = _read_float(
    "MT5_MAX_SPREAD_POINTS",
    500.0,
)

DEBUG = os.getenv(
    "DEBUG",
    "true",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def validate_telegram_config() -> None:
    errors: list[str] = []

    if TELEGRAM_API_ID <= 0:
        errors.append(
            "TELEGRAM_API_ID must be greater than zero."
        )

    if not TELEGRAM_API_HASH:
        errors.append(
            "TELEGRAM_API_HASH is required."
        )

    if not TELEGRAM_SESSION:
        errors.append(
            "TELEGRAM_SESSION is required."
        )

    if TELEGRAM_SIGNAL_GROUP_ID == 0:
        errors.append(
            "TELEGRAM_SIGNAL_GROUP_ID is required."
        )

    allowed_modes = {
        "DRY_RUN",
        "LIVE_DEMO",
    }

    if TELEGRAM_EXECUTION_MODE not in allowed_modes:
        errors.append(
            "TELEGRAM_EXECUTION_MODE must be "
            "DRY_RUN or LIVE_DEMO."
        )

    if (
        TELEGRAM_EXECUTION_MODE == "LIVE_DEMO"
        and not MT5_BROKER_GOLD_SYMBOL
    ):
        errors.append(
            "MT5_BROKER_GOLD_SYMBOL is required "
            "for LIVE_DEMO."
        )

    if MT5_MAX_SPREAD_POINTS <= 0:
        errors.append(
            "MT5_MAX_SPREAD_POINTS must be "
            "greater than zero."
        )

    if errors:
        joined_errors = "\n- ".join(errors)

        raise RuntimeError(
            "Invalid Telegram configuration:\n"
            f"- {joined_errors}"
        )