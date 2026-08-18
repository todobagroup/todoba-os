"""
TODOBA Trusted Agent Account Binding Provisioner

One-time deployment tool for creating the authoritative
Trusted Agent-to-MT5-account binding.

This tool is intentionally separate from Cloud startup.

Rules:
- missing store may be explicitly initialized here
- identical provisioning is idempotent
- conflicting re-binding is rejected
- secrets are never printed
"""

from pathlib import Path

from backend.config import (
    TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT,
    TODOBA_TRUSTED_AGENT_ID,
    validate_trusted_agent_config,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


DEFAULT_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "trusted_agent_account_bindings.json"
)


def provision_trusted_agent_account_binding(
    *,
    storage_path: Path,
    agent_id: str,
    account_fingerprint: str,
) -> str:
    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    if not store.is_ready():
        store.initialize_empty()

    return store.bind(
        agent_id=agent_id,
        account_fingerprint=account_fingerprint,
    )


def main() -> None:
    validate_trusted_agent_config()

    bound_account = (
        provision_trusted_agent_account_binding(
            storage_path=DEFAULT_STORAGE_PATH,
            agent_id=TODOBA_TRUSTED_AGENT_ID,
            account_fingerprint=(
                TODOBA_TRUSTED_AGENT_ACCOUNT_FINGERPRINT
            ),
        )
    )

    print(
        "Trusted Agent account binding provisioned."
    )
    print(
        f"Agent ID: {TODOBA_TRUSTED_AGENT_ID}"
    )
    print(
        f"Account fingerprint: {bound_account}"
    )
    print(
        f"Storage: {DEFAULT_STORAGE_PATH}"
    )


if __name__ == "__main__":
    main()