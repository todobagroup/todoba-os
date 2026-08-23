"""
TODOBA Executor Runtime Configuration Tests

Proof:

REMOTE_VPS
->
Cloud endpoint
+
Executor authentication
+
authorized Telegram technicians
->
validated remote Telegram runtime configuration

Trusted Agent fleet readiness is owned separately by
the commercial execution-target projection.
"""

import importlib
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


def reload_remote_config(
    monkeypatch: pytest.MonkeyPatch,
    **overrides: str,
):
    values = {
        "TELEGRAM_API_ID": "1",
        "TELEGRAM_API_HASH": "test-hash",
        "TELEGRAM_SESSION": "test-session",
        "TELEGRAM_SIGNAL_GROUP_ID": "-1001",
        "TELEGRAM_EXECUTION_MODE": "REMOTE_VPS",
        "TELEGRAM_AUTHORIZED_SENDER_IDS": (
            "101, 202"
        ),
        "MT5_MAX_SPREAD_POINTS": "100",
        "TODOBA_CLOUD_BASE_URL": (
            "https://api.todobagroup.com"
        ),
        "TODOBA_EXECUTOR_ID": (
            "telegram-executor-proof091"
        ),
        "TODOBA_EXECUTOR_SECRET": (
            "proof091-executor-secret"
        ),
        "TODOBA_TRUSTED_AGENT_ID": "",
        "TODOBA_TRUSTED_AGENT_SECRET": "",
        (
            "TODOBA_TRUSTED_AGENT_"
            "ACCOUNT_FINGERPRINT"
        ): "",
        (
            "TODOBA_EXECUTION_MISSION_"
            "SIGNING_SECRET"
        ): "",
        (
            "TODOBA_CONTROL_MISSION_"
            "SIGNING_SECRET"
        ): "",
        "TODOBA_TRUSTED_AGENTS_JSON": "",
        "TODOBA_EXECUTION_TARGETS_JSON": "",
    }

    values.update(
        overrides
    )

    for name, value in values.items():
        monkeypatch.setenv(
            name,
            value,
        )

    import backend.config as config

    return importlib.reload(
        config
    )


def test_executor_runtime_config_loads_remote_system_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = reload_remote_config(
        monkeypatch
    )

    assert loaded.TODOBA_CLOUD_BASE_URL == (
        "https://api.todobagroup.com"
    )

    assert loaded.TODOBA_EXECUTOR_ID == (
        "telegram-executor-proof091"
    )

    assert loaded.TODOBA_EXECUTOR_SECRET == (
        "proof091-executor-secret"
    )

    assert (
        loaded.TELEGRAM_AUTHORIZED_SENDER_IDS
        == (
            101,
            202,
        )
    )

    assert loaded.TODOBA_TRUSTED_AGENT_ID == ""
    assert loaded.TODOBA_TRUSTED_AGENTS_JSON == ""


def test_valid_remote_vps_config_is_accepted_without_legacy_fleet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = reload_remote_config(
        monkeypatch
    )

    loaded.validate_telegram_config()


@pytest.mark.parametrize(
    (
        "missing_name",
        "expected_message",
    ),
    [
        (
            "TODOBA_CLOUD_BASE_URL",
            "TODOBA_CLOUD_BASE_URL is required",
        ),
        (
            "TODOBA_EXECUTOR_ID",
            "TODOBA_EXECUTOR_ID is required",
        ),
        (
            "TODOBA_EXECUTOR_SECRET",
            "TODOBA_EXECUTOR_SECRET is required",
        ),
        (
            "TELEGRAM_AUTHORIZED_SENDER_IDS",
            (
                "TELEGRAM_AUTHORIZED_SENDER_IDS "
                "is required"
            ),
        ),
    ],
)
def test_remote_vps_config_rejects_missing_system_values(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
    expected_message: str,
) -> None:
    loaded = reload_remote_config(
        monkeypatch,
        **{
            missing_name: "",
        },
    )

    with pytest.raises(
        RuntimeError,
        match=expected_message,
    ):
        loaded.validate_telegram_config()


def test_remote_vps_validation_does_not_parse_legacy_fleet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = reload_remote_config(
        monkeypatch,
        TODOBA_TRUSTED_AGENTS_JSON=(
            "{legacy-json-is-not-valid"
        ),
        TODOBA_EXECUTION_TARGETS_JSON=(
            "{legacy-target-json-is-not-valid"
        ),
    )

    loaded.validate_telegram_config()


def test_config_rejects_invalid_authorized_sender_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "TELEGRAM_AUTHORIZED_SENDER_IDS "
            "must contain positive integers"
        ),
    ):
        reload_remote_config(
            monkeypatch,
            TELEGRAM_AUTHORIZED_SENDER_IDS=(
                "101,invalid"
            ),
        )
