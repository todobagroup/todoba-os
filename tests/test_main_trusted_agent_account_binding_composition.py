"""
TODOBA Trusted Agent Account Binding Startup Composition Tests

Locks the production composition for authoritative
Trusted Agent-to-MT5-account ownership at Cloud startup.
"""

import asyncio
from pathlib import Path

import pytest

from backend import main
from backend.config import (
    TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT,
    TODOBA_TRUSTED_AGENT_ID,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


def test_main_composes_trusted_agent_account_binding() -> None:
    assert (
        main.TRUSTED_AGENT_ACCOUNT_BINDING_STORAGE_PATH
        == (
            Path("data")
            / "trading"
            / "trusted_agent_account_bindings.json"
        )
    )

    assert isinstance(
        main.trusted_agent_account_binding_store,
        TrustedAgentAccountBindingStore,
    )

    assert (
        main.trusted_agent_account_binding_store.storage_path
        == main.TRUSTED_AGENT_ACCOUNT_BINDING_STORAGE_PATH
    )

    assert isinstance(
        main.trusted_agent_account_binding_guard,
        TrustedAgentAccountBindingGuard,
    )

    assert (
        main.trusted_agent_account_binding_guard.store
        is main.trusted_agent_account_binding_store
    )


def test_main_account_binding_check_uses_deployment_identity(
    monkeypatch,
) -> None:
    calls: list[
        tuple[str, str]
    ] = []

    def require_binding(
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> str:
        calls.append(
            (
                agent_id,
                account_fingerprint,
            )
        )

        return account_fingerprint

    monkeypatch.setattr(
        main.trusted_agent_account_binding_guard,
        "require_binding",
        require_binding,
    )

    result = (
        main._require_trusted_agent_account_binding()
    )

    assert result == (
        TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT
    )

    assert calls == [
        (
            TODOBA_TRUSTED_AGENT_ID,
            TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT,
        )
    ]


def test_main_account_binding_failure_stops_before_recovery(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def require_account_binding() -> str:
        calls.append(
            "account_binding"
        )

        raise RuntimeError(
            "binding rejected"
        )

    def restore_records() -> int:
        calls.append(
            "records"
        )

        return 0

    monkeypatch.setattr(
        main,
        "_require_trusted_agent_account_binding",
        require_account_binding,
    )

    monkeypatch.setattr(
        main.execution_mission_record_recovery,
        "restore",
        restore_records,
    )

    async def run_lifespan() -> None:
        async with main.lifespan(
            main.app
        ):
            pass

    with pytest.raises(
        RuntimeError,
        match="binding rejected",
    ):
        asyncio.run(
            run_lifespan()
        )

    assert calls == [
        "account_binding",
    ]