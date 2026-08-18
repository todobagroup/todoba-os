"""
TODOBA Trusted Agent Account Binding Guard

Enforces the expected Trusted Agent account ownership
binding during Cloud startup.

Responsibilities:
- require the durable binding store to be ready
- require an Agent to have an authoritative binding
- require the durable binding to match deployment config

This component does not:
- provision bindings
- initialize missing storage
- authenticate Agents
- receive HTTP requests
- manage replay floors
"""

from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)


class TrustedAgentAccountBindingGuard:
    """
    Fail-closed startup guard for Trusted Agent account
    ownership.
    """

    def __init__(
        self,
        store: TrustedAgentAccountBindingStore,
    ) -> None:
        if not isinstance(
            store,
            TrustedAgentAccountBindingStore,
        ):
            raise TypeError(
                "TrustedAgentAccountBindingGuard requires "
                "TrustedAgentAccountBindingStore."
            )

        self.store = store

    def require_binding(
        self,
        *,
        agent_id: str,
        account_fingerprint: str,
    ) -> str:
        if not self.store.is_ready():
            raise RuntimeError(
                "Trusted Agent account binding store "
                "is not initialized."
            )

        bound_account = (
            self.store.get_account_fingerprint(
                agent_id=agent_id,
            )
        )

        if bound_account is None:
            raise RuntimeError(
                "Trusted Agent has no authoritative "
                "account binding."
            )

        normalized_expected = (
            self._normalize_account_fingerprint(
                account_fingerprint
            )
        )

        if bound_account != normalized_expected:
            raise RuntimeError(
                "Trusted Agent account binding does not "
                "match deployment configuration."
            )

        return bound_account

    @staticmethod
    def _normalize_account_fingerprint(
        account_fingerprint: str,
    ) -> str:
        if not isinstance(
            account_fingerprint,
            str,
        ):
            raise TypeError(
                "account_fingerprint must be str."
            )

        normalized = (
            account_fingerprint.strip()
        )

        if not normalized:
            raise ValueError(
                "account_fingerprint must not be empty."
            )

        return normalized