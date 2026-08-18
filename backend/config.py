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


def _read_positive_int_tuple(
    name: str,
) -> tuple[int, ...]:
    raw_value = os.getenv(
        name,
        "",
    ).strip()

    if not raw_value:
        return ()

    values: list[int] = []

    for item in raw_value.split(","):
        normalized_item = item.strip()

        try:
            value = int(
                normalized_item
            )
        except ValueError as error:
            raise ValueError(
                f"{name} must contain positive "
                "integers separated by commas."
            ) from error

        if value <= 0:
            raise ValueError(
                f"{name} must contain positive "
                "integers separated by commas."
            )

        if value not in values:
            values.append(
                value
            )

    return tuple(
        values
    )


TODOBA_API_HOST = os.getenv(
    "TODOBA_API_HOST",
    "127.0.0.1",
).strip()

TODOBA_API_PORT = _read_int(
    "TODOBA_API_PORT",
    8000,
)

TODOBA_CLOUD_BASE_URL = os.getenv(
    "TODOBA_CLOUD_BASE_URL",
    "https://api.todobagroup.com",
).strip().rstrip("/")

TODOBA_RUNTIME_MODE = os.getenv(
    "TODOBA_RUNTIME_MODE",
    "LOCAL_TRADING",
).strip().upper()


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

TELEGRAM_AUTHORIZED_SENDER_IDS = (
    _read_positive_int_tuple(
        "TELEGRAM_AUTHORIZED_SENDER_IDS"
    )
)

MT5_BROKER_GOLD_SYMBOL = os.getenv(
    "MT5_BROKER_GOLD_SYMBOL",
    "GOLD.i#",
).strip()

MT5_MAX_SPREAD_POINTS = _read_float(
    "MT5_MAX_SPREAD_POINTS",
    500.0,
)

TODOBA_TRUSTED_AGENT_ID = os.getenv(
    "TODOBA_TRUSTED_AGENT_ID",
    "trusted-agent-001",
).strip()

TODOBA_TRUSTED_AGENT_SECRET = os.getenv(
    "TODOBA_TRUSTED_AGENT_SECRET",
    "",
).strip()

TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT = os.getenv(
    "TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT",
    "",
).strip()

TODOBA_EXECUTION_MISSION_SIGNING_SECRET = os.getenv(
    "TODOBA_EXECUTION_MISSION_SIGNING_SECRET",
    "",
).strip()

TODOBA_CONTROL_MISSION_SIGNING_SECRET = os.getenv(
    "TODOBA_CONTROL_MISSION_SIGNING_SECRET",
    "",
).strip()

TODOBA_EXECUTOR_ID = os.getenv(
    "TODOBA_EXECUTOR_ID",
    "telegram-executor-001",
).strip()

TODOBA_EXECUTOR_SECRET = os.getenv(
    "TODOBA_EXECUTOR_SECRET",
    "",
).strip()

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

    if not TELEGRAM_AUTHORIZED_SENDER_IDS:
        errors.append(
            "TELEGRAM_AUTHORIZED_SENDER_IDS "
            "is required."
        )

    allowed_modes = {
        "DRY_RUN",
        "LIVE_DEMO",
        "REMOTE_VPS",
    }

    if TELEGRAM_EXECUTION_MODE not in allowed_modes:
        errors.append(
            "TELEGRAM_EXECUTION_MODE must be "
            "DRY_RUN, LIVE_DEMO, or REMOTE_VPS."
        )

    if TELEGRAM_EXECUTION_MODE == "REMOTE_VPS":
        if not TODOBA_CLOUD_BASE_URL:
            errors.append(
                "TODOBA_CLOUD_BASE_URL is required "
                "for REMOTE_VPS."
            )

        if not TODOBA_TRUSTED_AGENT_ID:
            errors.append(
                "TODOBA_TRUSTED_AGENT_ID is required "
                "for REMOTE_VPS."
            )

        if not TODOBA_EXECUTOR_ID:
            errors.append(
                "TODOBA_EXECUTOR_ID is required "
                "for REMOTE_VPS."
            )

        if not TODOBA_EXECUTOR_SECRET:
            errors.append(
                "TODOBA_EXECUTOR_SECRET is required "
                "for REMOTE_VPS."
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
        joined_errors = "\n- ".join(
            errors
        )

        raise RuntimeError(
            "Invalid Telegram configuration:\n"
            f"- {joined_errors}"
        )


def validate_trusted_agent_config() -> None:
    errors: list[str] = []

    if not TODOBA_TRUSTED_AGENT_ID:
        errors.append(
            "TODOBA_TRUSTED_AGENT_ID is required."
        )

    if not TODOBA_TRUSTED_AGENT_SECRET:
        errors.append(
            "TODOBA_TRUSTED_AGENT_SECRET is required."
        )

    if not TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT:
        errors.append(
            "TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT "
            "is required."
        )

    if not TODOBA_EXECUTION_MISSION_SIGNING_SECRET:
        errors.append(
            "TODOBA_EXECUTION_MISSION_SIGNING_SECRET "
            "is required."
        )

    if not TODOBA_CONTROL_MISSION_SIGNING_SECRET:
        errors.append(
            "TODOBA_CONTROL_MISSION_SIGNING_SECRET "
            "is required."
        )

    if errors:
        joined_errors = "\n- ".join(
            errors
        )

        raise RuntimeError(
            "Invalid Trusted Agent configuration:\n"
            f"- {joined_errors}"
        )