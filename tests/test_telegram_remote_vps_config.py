"""
TODOBA Telegram REMOTE_VPS Configuration Tests

Proof:

REMOTE_VPS
+
authorized Telegram technician
->
validate_telegram_config()
->
accepted
"""

import importlib
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


def test_remote_vps_execution_mode_is_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = {
        "TELEGRAM_EXECUTION_MODE": "REMOTE_VPS",
        "TELEGRAM_API_ID": "1",
        "TELEGRAM_API_HASH": "test-hash",
        "TELEGRAM_SESSION": "test-session",
        "TELEGRAM_SIGNAL_GROUP_ID": "-1001",
        "TELEGRAM_AUTHORIZED_SENDER_IDS": (
            "101,202"
        ),
        "MT5_MAX_SPREAD_POINTS": "100",
        "TODOBA_CLOUD_BASE_URL": (
            "https://api.todobagroup.com"
        ),
        "TODOBA_TRUSTED_AGENT_ID": (
            "trusted-agent-001"
        ),
        "TODOBA_EXECUTOR_ID": (
            "telegram-executor-001"
        ),
        "TODOBA_EXECUTOR_SECRET": (
            "proof-executor-secret"
        ),
    }

    for name, value in environment.items():
        monkeypatch.setenv(
            name,
            value,
        )

    import backend.config as config

    loaded = importlib.reload(
        config
    )

    loaded.validate_telegram_config()

    assert loaded.TELEGRAM_EXECUTION_MODE == (
        "REMOTE_VPS"
    )

    assert (
        loaded.TELEGRAM_AUTHORIZED_SENDER_IDS
        == (
            101,
            202,
        )
    )