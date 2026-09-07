"""
TODOBA Customer VPS Connect Deployment Resolver

Read-only server-side authority bridge:

trusted customer_id
+ observed canonical MT5 account_fingerprint
-> exactly one existing customer deployment

Security boundary:
- customer_id must already come from trusted server-side authorization
- account_fingerprint must come from customer MT5 preflight
- caller never supplies deployment_id or agent_id
- no deployment, entitlement, package, secret, MT5, or VPS mutation
- ambiguous authoritative matches fail closed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _normalize_required_string(
    value: object,
    *,
    name: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{name} is required.")

    if normalized != value:
        raise ValueError(f"{name} must be normalized.")

    return normalized


@dataclass(frozen=True, slots=True)
class CustomerVPSConnectDeploymentResolution:
    customer_id: str
    deployment_id: str
    agent_id: str
    account_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "customer_id",
            "deployment_id",
            "agent_id",
            "account_fingerprint",
        ):
            object.__setattr__(
                self,
                name,
                _normalize_required_string(
                    getattr(self, name),
                    name=name,
                ),
            )


class CustomerVPSConnectDeploymentResolver:
    """
    Resolve one existing deployment without creating authority.

    This owner performs only read operations against:
    - CustomerDeploymentRegistry
    - TrustedAgentAccountBindingStore
    """

    def __init__(
        self,
        *,
        deployment_registry: Any,
        account_binding_store: Any,
    ) -> None:
        if not callable(
            getattr(deployment_registry, "all", None)
        ):
            raise TypeError(
                "deployment_registry must expose all()."
            )

        if not callable(
            getattr(
                account_binding_store,
                "get_account_fingerprint",
                None,
            )
        ):
            raise TypeError(
                "account_binding_store must expose "
                "get_account_fingerprint()."
            )

        self._deployment_registry = deployment_registry
        self._account_binding_store = account_binding_store

    def resolve(
        self,
        *,
        customer_id: str,
        account_fingerprint: str,
    ) -> CustomerVPSConnectDeploymentResolution | None:
        normalized_customer_id = _normalize_required_string(
            customer_id,
            name="customer_id",
        )
        normalized_account_fingerprint = (
            _normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        deployments = self._deployment_registry.all()

        try:
            iterator = iter(deployments)
        except TypeError as exc:
            raise RuntimeError(
                "Deployment registry returned invalid collection."
            ) from exc

        matches: list[
            CustomerVPSConnectDeploymentResolution
        ] = []

        for deployment in iterator:
            deployment_customer_id = (
                _normalize_required_string(
                    getattr(
                        deployment,
                        "customer_id",
                        None,
                    ),
                    name="deployment.customer_id",
                )
            )

            if (
                deployment_customer_id
                != normalized_customer_id
            ):
                continue

            deployment_id = _normalize_required_string(
                getattr(
                    deployment,
                    "deployment_id",
                    None,
                ),
                name="deployment.deployment_id",
            )
            agent_id = _normalize_required_string(
                getattr(
                    deployment,
                    "agent_id",
                    None,
                ),
                name="deployment.agent_id",
            )

            bound_account_fingerprint = (
                self._account_binding_store
                .get_account_fingerprint(
                    agent_id=agent_id
                )
            )

            if bound_account_fingerprint is None:
                continue

            bound_account_fingerprint = (
                _normalize_required_string(
                    bound_account_fingerprint,
                    name=(
                        "bound_account_fingerprint"
                    ),
                )
            )

            if (
                bound_account_fingerprint
                != normalized_account_fingerprint
            ):
                continue

            matches.append(
                CustomerVPSConnectDeploymentResolution(
                    customer_id=deployment_customer_id,
                    deployment_id=deployment_id,
                    agent_id=agent_id,
                    account_fingerprint=(
                        bound_account_fingerprint
                    ),
                )
            )

        if not matches:
            return None

        if len(matches) != 1:
            raise RuntimeError(
                "VPS Connect deployment resolution "
                "is ambiguous."
            )

        return matches[0]
