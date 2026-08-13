"""
TODOBA Telegram REMOTE_VPS Configuration Tests

Proof:

TELEGRAM_EXECUTION_MODE=REMOTE_VPS
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
    monkeypatch.setenv(
        "TELEGRAM_EXECUTION_MODE",
        "REMOTE_VPS",
    )

    monkeypatch.setenv(
        "TELEGRAM_API_ID",
        "1",
    )

    monkeypatch.setenv(
        "TELEGRAM_API_HASH",
        "test-hash",
    )

    monkeypatch.setenv(
        "TELEGRAM_SESSION",
        "test-session",
    )

    monkeypatch.setenv(
        "TELEGRAM_SIGNAL_GROUP_ID",
        "1",
    )

    import backend.config as config

    loaded = importlib.reload(
        config
    )

    loaded.validate_telegram_config()

    assert loaded.TELEGRAM_EXECUTION_MODE == (
        "REMOTE_VPS"
    )