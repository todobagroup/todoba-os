"""
TODOBA Telegram Dispatch Startup Recovery Tests

Proof:

REMOTE_VPS startup must compose TelegramDispatchRecovery
and run durable dispatch recovery before the Telegram
client starts receiving new messages.

Required startup order:

validate configuration
->
recover durable Telegram dispatches
->
create Telegram client
->
register Telegram handlers
->
start Telegram client
->
run until disconnected
"""

import asyncio
import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.integrations.telegram_dispatch_recovery import (
    TelegramDispatchRecovery,
)


TRUSTED_AGENTS = [
    {
        "agent_id": "trusted-agent-001",
        "agent_secret": "agent-secret-a",
        "account_fingerprint": "account-a",
        "execution_mission_signing_secret": (
            "execution-signing-a"
        ),
        "control_mission_signing_secret": (
            "control-signing-a"
        ),
    },
]


EXECUTION_TARGETS = [
    {
        "agent_id": "trusted-agent-001",
        "account_fingerprint": "account-a",
    },
]


def configure_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = {
        "TELEGRAM_API_ID": "1",
        "TELEGRAM_API_HASH": "test-hash",
        "TELEGRAM_SESSION": "test-session",
        "TELEGRAM_SIGNAL_GROUP_ID": "-1001",
        "TELEGRAM_EXECUTION_MODE": "REMOTE_VPS",
        "TELEGRAM_AUTHORIZED_SENDER_IDS": "1",
        "MT5_MAX_SPREAD_POINTS": "100",
        "TODOBA_CLOUD_BASE_URL": (
            "https://api.todobagroup.com"
        ),
        "TODOBA_EXECUTOR_ID": (
            "telegram-executor-startup-recovery"
        ),
        "TODOBA_EXECUTOR_SECRET": (
            "startup-recovery-secret"
        ),
        "TODOBA_TRUSTED_AGENT_ID": "",
        "TODOBA_TRUSTED_AGENTS_JSON": (
            json.dumps(
                TRUSTED_AGENTS
            )
        ),
        "TODOBA_EXECUTION_TARGETS_JSON": (
            json.dumps(
                EXECUTION_TARGETS
            )
        ),
    }

    for name, value in environment.items():
        monkeypatch.setenv(
            name,
            value,
        )


def load_listener(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    configure_environment(
        monkeypatch
    )

    import backend.config as config

    importlib.reload(
        config
    )

    import backend.integrations.telegram_dispatch_progress_store as progress_store_module

    real_progress_store = (
        progress_store_module.TelegramDispatchProgressStore
    )

    def build_test_progress_store(
        *,
        storage_path: Path,
    ):
        return real_progress_store(
            storage_path=(
                tmp_path
                / "telegram_dispatch_progress.json"
            )
        )

    monkeypatch.setattr(
        progress_store_module,
        "TelegramDispatchProgressStore",
        build_test_progress_store,
    )

    sys.modules.pop(
        "backend.integrations.telegram_listener",
        None,
    )

    return importlib.import_module(
        "backend.integrations.telegram_listener"
    )


def test_remote_vps_listener_composes_dispatch_recovery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
    )

    assert isinstance(
        listener.remote_dispatch_recovery,
        TelegramDispatchRecovery,
    )

    assert (
        listener.remote_dispatch_recovery.progress_store
        is listener.remote_dispatch_progress_store
    )

    assert (
        listener.remote_dispatch_recovery
        .execution_target_registry
        is listener.remote_execution_target_registry
    )

    assert (
        listener.remote_dispatch_recovery.http_client
        is listener.remote_http_client
    )


class FakeRecovery:
    def __init__(
        self,
        calls: list[str],
    ) -> None:
        self.calls = calls

    def restore(
        self,
    ) -> int:
        self.calls.append(
            "recovery"
        )

        return 0


class FakeTelegramClient:
    def __init__(
        self,
        calls: list[str],
    ) -> None:
        self.calls = calls

    async def start(
        self,
    ) -> None:
        self.calls.append(
            "client_start"
        )

    async def run_until_disconnected(
        self,
    ) -> None:
        self.calls.append(
            "run_until_disconnected"
        )

    def is_connected(
        self,
    ) -> bool:
        return False

    async def disconnect(
        self,
    ) -> None:
        self.calls.append(
            "disconnect"
        )


def test_remote_vps_startup_recovers_before_telegram_client_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    listener = load_listener(
        monkeypatch,
        tmp_path,
    )

    calls: list[str] = []

    fake_recovery = FakeRecovery(
        calls
    )

    fake_client = FakeTelegramClient(
        calls
    )

    def validate_config() -> None:
        calls.append(
            "validate"
        )

    def create_client():
        calls.append(
            "create_client"
        )

        return fake_client

    async def register_handlers() -> None:
        calls.append(
            "register_handlers"
        )

    monkeypatch.setattr(
        listener,
        "validate_telegram_config",
        validate_config,
    )

    monkeypatch.setattr(
        listener,
        "remote_dispatch_recovery",
        fake_recovery,
        raising=False,
    )

    monkeypatch.setattr(
        listener,
        "create_telegram_client",
        create_client,
    )

    monkeypatch.setattr(
        listener,
        "register_handlers",
        register_handlers,
    )

    asyncio.run(
        listener.main()
    )

    assert calls == [
        "validate",
        "recovery",
        "create_client",
        "register_handlers",
        "client_start",
        "run_until_disconnected",
    ]