"""
TODOBA Application Configuration

Loads runtime configuration from the repository .env file.

Secrets must never be committed to Git.
"""

import json
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

TODOBA_TRUSTED_AGENTS_JSON = os.getenv(
    "TODOBA_TRUSTED_AGENTS_JSON",
    "",
).strip()

TODOBA_EXECUTION_TARGETS_JSON = os.getenv(
    "TODOBA_EXECUTION_TARGETS_JSON",
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

TODOBA_CONTROL_PLANE_DATA_ROOT = Path(
    os.getenv(
        "TODOBA_CONTROL_PLANE_DATA_ROOT",
        "data",
    ).strip()
)

TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME = (
    "TODOBA_CUSTOMER_PACKAGE_ROOT"
)


def get_customer_package_root() -> Path:
    """
    Return the explicit external root containing
    already-published customer deployment packages.

    Runtime configuration must never create this directory.
    Package publication/build tooling owns filesystem creation.
    """

    raw_value = os.getenv(
        TODOBA_CUSTOMER_PACKAGE_ROOT_ENV_NAME,
        "",
    ).strip()

    if not raw_value:
        raise RuntimeError(
            "TODOBA_CUSTOMER_PACKAGE_ROOT is required."
        )

    configured_path = Path(
        raw_value
    )

    if not configured_path.is_absolute():
        raise ValueError(
            "TODOBA_CUSTOMER_PACKAGE_ROOT must be "
            "an absolute path."
        )

    resolved_path = (
        configured_path.resolve()
    )

    if (
        resolved_path == BASE_DIR
        or BASE_DIR in resolved_path.parents
    ):
        raise ValueError(
            "TODOBA_CUSTOMER_PACKAGE_ROOT must be "
            "outside the repository."
        )

    return resolved_path


TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY = os.getenv(
    "TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY",
    "",
)

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


def get_trusted_agent_deployments() -> tuple[
    dict[str, str],
    ...,
]:
    """
    Return configured Trusted Agent deployments.

    Multi-Agent JSON configuration takes precedence.
    When it is absent, the legacy single-Agent
    environment variables remain supported.
    """

    if not TODOBA_TRUSTED_AGENTS_JSON:
        return (
            {
                "agent_id": TODOBA_TRUSTED_AGENT_ID,
                "agent_secret": TODOBA_TRUSTED_AGENT_SECRET,
                "account_fingerprint": (
                    TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT
                ),
                "execution_mission_signing_secret": (
                    TODOBA_EXECUTION_MISSION_SIGNING_SECRET
                ),
                "control_mission_signing_secret": (
                    TODOBA_CONTROL_MISSION_SIGNING_SECRET
                ),
            },
        )

    try:
        payload = json.loads(
            TODOBA_TRUSTED_AGENTS_JSON
        )
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "TODOBA_TRUSTED_AGENTS_JSON must contain "
            "valid JSON."
        ) from error

    if not isinstance(
        payload,
        list,
    ):
        raise RuntimeError(
            "TODOBA_TRUSTED_AGENTS_JSON must contain "
            "a JSON list."
        )

    if not payload:
        raise RuntimeError(
            "TODOBA_TRUSTED_AGENTS_JSON must contain "
            "at least one Trusted Agent."
        )

    deployments: list[
        dict[str, str]
    ] = []

    known_agent_ids: set[str] = set()

    required_fields = {
        "agent_id",
        "agent_secret",
        "account_fingerprint",
        "execution_mission_signing_secret",
        "control_mission_signing_secret",
    }

    for item in payload:
        if not isinstance(
            item,
            dict,
        ):
            raise RuntimeError(
                "TODOBA_TRUSTED_AGENTS_JSON entries "
                "must be JSON objects."
            )

        missing_fields = (
            required_fields
            - set(
                item.keys()
            )
        )

        extra_fields = (
            set(
                item.keys()
            )
            - required_fields
        )

        if missing_fields:
            missing_field = sorted(
                missing_fields
            )[0]

            raise RuntimeError(
                "TODOBA_TRUSTED_AGENTS_JSON entry "
                f"is missing {missing_field}."
            )

        if extra_fields:
            raise RuntimeError(
                "TODOBA_TRUSTED_AGENTS_JSON entries "
                "contain unsupported fields."
            )

        agent_id = item[
            "agent_id"
        ]

        agent_secret = item[
            "agent_secret"
        ]

        account_fingerprint = item[
            "account_fingerprint"
        ]

        execution_mission_signing_secret = item[
            "execution_mission_signing_secret"
        ]

        control_mission_signing_secret = item[
            "control_mission_signing_secret"
        ]

        if not isinstance(
            agent_id,
            str,
        ):
            raise RuntimeError(
                "Trusted Agent agent_id must be str."
            )

        if not isinstance(
            agent_secret,
            str,
        ):
            raise RuntimeError(
                "Trusted Agent agent_secret must be str."
            )

        if not isinstance(
            account_fingerprint,
            str,
        ):
            raise RuntimeError(
                "Trusted Agent account_fingerprint "
                "must be str."
            )

        if not isinstance(
            execution_mission_signing_secret,
            str,
        ):
            raise RuntimeError(
                "Trusted Agent "
                "execution_mission_signing_secret "
                "must be str."
            )

        if not isinstance(
            control_mission_signing_secret,
            str,
        ):
            raise RuntimeError(
                "Trusted Agent "
                "control_mission_signing_secret "
                "must be str."
            )

        normalized_agent_id = (
            agent_id.strip()
        )

        normalized_agent_secret = (
            agent_secret
        )

        normalized_account_fingerprint = (
            account_fingerprint.strip()
        )

        normalized_execution_signing_secret = (
            execution_mission_signing_secret
        )

        normalized_control_signing_secret = (
            control_mission_signing_secret
        )

        if not normalized_agent_id:
            raise RuntimeError(
                "Trusted Agent agent_id is required."
            )

        if normalized_agent_secret == "":
            raise RuntimeError(
                "Trusted Agent agent_secret is required."
            )

        if not normalized_account_fingerprint:
            raise RuntimeError(
                "Trusted Agent account_fingerprint "
                "is required."
            )

        if normalized_execution_signing_secret == "":
            raise RuntimeError(
                "Trusted Agent "
                "execution_mission_signing_secret "
                "is required."
            )

        if normalized_control_signing_secret == "":
            raise RuntimeError(
                "Trusted Agent "
                "control_mission_signing_secret "
                "is required."
            )

        if normalized_agent_id in known_agent_ids:
            raise RuntimeError(
                "Duplicate Trusted Agent ID "
                "in TODOBA_TRUSTED_AGENTS_JSON."
            )

        known_agent_ids.add(
            normalized_agent_id
        )

        deployments.append(
            {
                "agent_id": normalized_agent_id,
                "agent_secret": normalized_agent_secret,
                "account_fingerprint": (
                    normalized_account_fingerprint
                ),
                "execution_mission_signing_secret": (
                    normalized_execution_signing_secret
                ),
                "control_mission_signing_secret": (
                    normalized_control_signing_secret
                ),
            }
        )

    return tuple(
        deployments
    )

def get_execution_targets() -> tuple[
    dict[str, str],
    ...,
]:
    """
    Return configured remote execution routing targets.

    Trusted Agent deployments define security ownership.
    Execution targets independently define which configured
    Agents/accounts receive trading signals.

    Legacy single-Agent configuration remains supported.
    """

    if not TODOBA_TRUSTED_AGENTS_JSON:
        return (
            {
                "agent_id": TODOBA_TRUSTED_AGENT_ID,
                "account_fingerprint": (
                    TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT
                ),
            },
        )

    deployments = (
        get_trusted_agent_deployments()
    )

    if not TODOBA_EXECUTION_TARGETS_JSON:
        raise RuntimeError(
            "TODOBA_EXECUTION_TARGETS_JSON is required "
            "when TODOBA_TRUSTED_AGENTS_JSON is configured."
        )

    try:
        payload = json.loads(
            TODOBA_EXECUTION_TARGETS_JSON
        )
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "TODOBA_EXECUTION_TARGETS_JSON must contain "
            "valid JSON."
        ) from error

    if not isinstance(
        payload,
        list,
    ):
        raise RuntimeError(
            "TODOBA_EXECUTION_TARGETS_JSON must contain "
            "a JSON list."
        )

    if not payload:
        raise RuntimeError(
            "TODOBA_EXECUTION_TARGETS_JSON must contain "
            "at least one execution target."
        )

    configured_deployments = {
        deployment["agent_id"]: deployment
        for deployment in deployments
    }

    known_target_agent_ids: set[str] = set()

    targets: list[
        dict[str, str]
    ] = []

    required_fields = {
        "agent_id",
        "account_fingerprint",
    }

    for item in payload:
        if not isinstance(
            item,
            dict,
        ):
            raise RuntimeError(
                "TODOBA_EXECUTION_TARGETS_JSON entries "
                "must be JSON objects."
            )

        missing_fields = (
            required_fields
            - set(
                item.keys()
            )
        )

        extra_fields = (
            set(
                item.keys()
            )
            - required_fields
        )

        if missing_fields:
            missing_field = sorted(
                missing_fields
            )[0]

            raise RuntimeError(
                "TODOBA_EXECUTION_TARGETS_JSON entry "
                f"is missing {missing_field}."
            )

        if extra_fields:
            raise RuntimeError(
                "TODOBA_EXECUTION_TARGETS_JSON entries "
                "contain unsupported fields."
            )

        agent_id = item[
            "agent_id"
        ]

        account_fingerprint = item[
            "account_fingerprint"
        ]

        if not isinstance(
            agent_id,
            str,
        ):
            raise RuntimeError(
                "Execution target agent_id must be str."
            )

        if not isinstance(
            account_fingerprint,
            str,
        ):
            raise RuntimeError(
                "Execution target account_fingerprint "
                "must be str."
            )

        normalized_agent_id = (
            agent_id.strip()
        )

        normalized_account_fingerprint = (
            account_fingerprint.strip()
        )

        if not normalized_agent_id:
            raise RuntimeError(
                "Execution target agent_id is required."
            )

        if not normalized_account_fingerprint:
            raise RuntimeError(
                "Execution target account_fingerprint "
                "is required."
            )

        deployment = (
            configured_deployments.get(
                normalized_agent_id
            )
        )

        if deployment is None:
            raise RuntimeError(
                "Execution target Agent is not a "
                "configured Trusted Agent."
            )

        if (
            deployment["account_fingerprint"]
            != normalized_account_fingerprint
        ):
            raise RuntimeError(
                "Execution target account_fingerprint "
                "does not match the configured Trusted "
                "Agent deployment."
            )

        if (
            normalized_agent_id
            in known_target_agent_ids
        ):
            raise RuntimeError(
                "Duplicate execution target Agent "
                "in TODOBA_EXECUTION_TARGETS_JSON."
            )

        known_target_agent_ids.add(
            normalized_agent_id
        )

        targets.append(
            {
                "agent_id": normalized_agent_id,
                "account_fingerprint": (
                    normalized_account_fingerprint
                ),
            }
        )

    return tuple(
        targets
    )

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

    if TODOBA_TRUSTED_AGENTS_JSON:
        get_trusted_agent_deployments()
    else:
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