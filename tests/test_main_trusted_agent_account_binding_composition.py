"""
TODOBA Trusted Agent Multi-Agent Startup Composition Tests

Locks the production composition for:
- Trusted Agent credential registry
- multi-Agent authentication
- authoritative Agent-to-account ownership checks
- fail-closed Cloud startup
"""

import asyncio
from pathlib import Path

import pytest

from backend import main
from backend.config import (
    TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT,
    TODOBA_TRUSTED_AGENT_ID,
    TODOBA_TRUSTED_AGENT_SECRET,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)
from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
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


def test_main_composes_trusted_agent_credential_registry() -> None:
    assert isinstance(
        main.trusted_agent_credential_registry,
        TrustedAgentCredentialRegistry,
    )

    assert (
        main.trusted_agent_credential_registry.get_secret(
            agent_id=TODOBA_TRUSTED_AGENT_ID
        )
        == TODOBA_TRUSTED_AGENT_SECRET
    )

    assert isinstance(
        main.trusted_agent_authenticator,
        TrustedAgentAuthenticator,
    )

    assert main.trusted_agent_authenticator.authenticate(
        agent_id=TODOBA_TRUSTED_AGENT_ID,
        authorization=(
            f"Bearer {TODOBA_TRUSTED_AGENT_SECRET}"
        ),
    )


def test_main_builds_registry_for_multiple_deployments() -> None:
    deployments = (
        {
            "agent_id": "trusted-agent-001",
            "agent_secret": "secret-a",
            "account_fingerprint": "account-a",
        },
        {
            "agent_id": "trusted-agent-002",
            "agent_secret": "secret-b",
            "account_fingerprint": "account-b",
        },
    )

    registry = (
        main._build_trusted_agent_credential_registry(
            deployments
        )
    )

    assert registry.size() == 2

    assert (
        registry.get_secret(
            agent_id="trusted-agent-001"
        )
        == "secret-a"
    )

    assert (
        registry.get_secret(
            agent_id="trusted-agent-002"
        )
        == "secret-b"
    )


def test_main_account_binding_check_uses_all_deployments(
    monkeypatch,
) -> None:
    calls: list[
        tuple[str, str]
    ] = []

    deployments = (
        {
            "agent_id": "trusted-agent-001",
            "agent_secret": "secret-a",
            "account_fingerprint": "account-a",
        },
        {
            "agent_id": "trusted-agent-002",
            "agent_secret": "secret-b",
            "account_fingerprint": "account-b",
        },
    )

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
        main,
        "trusted_agent_deployments",
        deployments,
        raising=False,
    )

    monkeypatch.setattr(
        main.trusted_agent_account_binding_guard,
        "require_binding",
        require_binding,
    )

    result = (
        main._require_trusted_agent_account_bindings()
    )

    assert result == (
        "account-a",
        "account-b",
    )

    assert calls == [
        (
            "trusted-agent-001",
            "account-a",
        ),
        (
            "trusted-agent-002",
            "account-b",
        ),
    ]


def test_main_account_binding_failure_stops_before_recovery(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def require_account_bindings() -> tuple[
        str,
        ...,
    ]:
        calls.append(
            "account_bindings"
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
        "_require_trusted_agent_account_bindings",
        require_account_bindings,
        raising=False,
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
        "account_bindings",
    ]