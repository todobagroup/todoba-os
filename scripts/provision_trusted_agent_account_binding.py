"""
TODOBA Trusted Agent Account Binding Provisioner

One-time deployment tool for creating authoritative
Trusted Agent-to-MT5-account bindings.

This tool is intentionally separate from Cloud startup.

Rules:
- missing store may be explicitly initialized here
- single-Agent legacy provisioning remains supported
- multi-Agent runtime configuration provisions all Agents
- all configured bindings are conflict-checked before writes
- identical provisioning is idempotent
- conflicting re-binding is rejected
- secrets are never printed
"""

from pathlib import Path

from backend.config import (
    get_trusted_agent_deployments,
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
    """
    Provision one authoritative Agent/account binding.

    Kept as the compatibility API for callers that own
    one explicit deployment.
    """

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    if not store.is_ready():
        store.initialize_empty()

    return store.bind(
        agent_id=agent_id,
        account_fingerprint=account_fingerprint,
    )


def provision_trusted_agent_account_bindings(
    *,
    storage_path: Path,
    deployments: tuple[
        dict[str, str],
        ...,
    ],
) -> tuple[
    str,
    ...,
]:
    """
    Provision all configured Trusted Agent bindings.

    Every requested Agent/account pair is checked against
    durable authoritative state before any new binding is
    written. This prevents a later conflict from leaving
    only part of a deployment fleet provisioned.
    """

    if not isinstance(
        deployments,
        tuple,
    ):
        raise TypeError(
            "deployments must be tuple."
        )

    if not deployments:
        raise ValueError(
            "deployments must not be empty."
        )

    normalized_deployments: list[
        tuple[str, str]
    ] = []

    known_agent_ids: set[str] = set()

    for deployment in deployments:
        if not isinstance(
            deployment,
            dict,
        ):
            raise TypeError(
                "Trusted Agent deployment must be dict."
            )

        if "agent_id" not in deployment:
            raise ValueError(
                "Trusted Agent deployment requires agent_id."
            )

        if "account_fingerprint" not in deployment:
            raise ValueError(
                "Trusted Agent deployment requires "
                "account_fingerprint."
            )

        agent_id = deployment[
            "agent_id"
        ]

        account_fingerprint = deployment[
            "account_fingerprint"
        ]

        if not isinstance(
            agent_id,
            str,
        ):
            raise TypeError(
                "Trusted Agent agent_id must be str."
            )

        if not isinstance(
            account_fingerprint,
            str,
        ):
            raise TypeError(
                "Trusted Agent account_fingerprint "
                "must be str."
            )

        normalized_agent_id = (
            agent_id.strip()
        )

        normalized_account_fingerprint = (
            account_fingerprint.strip()
        )

        if not normalized_agent_id:
            raise ValueError(
                "Trusted Agent agent_id is required."
            )

        if not normalized_account_fingerprint:
            raise ValueError(
                "Trusted Agent account_fingerprint "
                "is required."
            )

        if (
            normalized_agent_id
            in known_agent_ids
        ):
            raise ValueError(
                "Duplicate Trusted Agent deployment."
            )

        known_agent_ids.add(
            normalized_agent_id
        )

        normalized_deployments.append(
            (
                normalized_agent_id,
                normalized_account_fingerprint,
            )
        )

    store = TrustedAgentAccountBindingStore(
        storage_path
    )

    if not store.is_ready():
        store.initialize_empty()

    for (
        agent_id,
        account_fingerprint,
    ) in normalized_deployments:
        existing = (
            store.get_account_fingerprint(
                agent_id=agent_id
            )
        )

        if (
            existing is not None
            and existing != account_fingerprint
        ):
            raise ValueError(
                "Trusted Agent is already bound "
                "to a different account."
            )

    bound_accounts: list[str] = []

    for (
        agent_id,
        account_fingerprint,
    ) in normalized_deployments:
        bound_accounts.append(
            store.bind(
                agent_id=agent_id,
                account_fingerprint=(
                    account_fingerprint
                ),
            )
        )

    return tuple(
        bound_accounts
    )


def main() -> None:
    validate_trusted_agent_config()

    deployments = (
        get_trusted_agent_deployments()
    )

    bound_accounts = (
        provision_trusted_agent_account_bindings(
            storage_path=DEFAULT_STORAGE_PATH,
            deployments=deployments,
        )
    )

    print(
        "Trusted Agent account bindings provisioned."
    )

    print(
        f"Deployment count: {len(deployments)}"
    )

    for deployment, bound_account in zip(
        deployments,
        bound_accounts,
        strict=True,
    ):
        print(
            f"Agent ID: {deployment['agent_id']}"
        )

        print(
            f"Account fingerprint: {bound_account}"
        )

    print(
        f"Storage: {DEFAULT_STORAGE_PATH}"
    )


if __name__ == "__main__":
    main()