from __future__ import annotations

from typing import Callable


def _normalize_required_string(
    value: str,
    *,
    name: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(
            f"{name} must be str."
        )

    if not value:
        raise ValueError(
            f"{name} must not be empty."
        )

    if value.strip() != value:
        raise ValueError(
            f"{name} must be normalized."
        )

    return value


class CustomerVPSConnectGrantCompositionService:
    """
    Compose trusted BOUND Setup authority with the
    observed MT5 account before issuing a VPS Connect grant.

    Caller supplies only:
    - activation_code
    - account_fingerprint

    Customer, deployment, and agent identities are always
    server-derived.
    """

    def __init__(
        self,
        *,
        authorize_bound_access_code: Callable,
        resolve_deployment: Callable,
        issue_grant: Callable,
    ) -> None:
        for name, dependency in (
            (
                "authorize_bound_access_code",
                authorize_bound_access_code,
            ),
            (
                "resolve_deployment",
                resolve_deployment,
            ),
            (
                "issue_grant",
                issue_grant,
            ),
        ):
            if not callable(dependency):
                raise TypeError(
                    f"{name} must be callable."
                )

        self._authorize_bound_access_code = (
            authorize_bound_access_code
        )
        self._resolve_deployment = (
            resolve_deployment
        )
        self._issue_grant = issue_grant

    def issue(
        self,
        *,
        activation_code: str,
        account_fingerprint: str,
    ):
        normalized_activation_code = (
            _normalize_required_string(
                activation_code,
                name="activation_code",
            )
        )
        normalized_account_fingerprint = (
            _normalize_required_string(
                account_fingerprint,
                name="account_fingerprint",
            )
        )

        bound = self._authorize_bound_access_code(
            activation_code=(
                normalized_activation_code
            )
        )

        customer_id = _normalize_required_string(
            getattr(
                bound,
                "customer_id",
                None,
            ),
            name="customer_id",
        )
        bound_deployment_id = (
            _normalize_required_string(
                getattr(
                    bound,
                    "deployment_id",
                    None,
                ),
                name="deployment_id",
            )
        )

        resolution = self._resolve_deployment(
            customer_id=customer_id,
            account_fingerprint=(
                normalized_account_fingerprint
            ),
        )

        if resolution is None:
            raise ValueError(
                "Customer VPS Connect deployment "
                "could not be resolved."
            )

        resolved_customer_id = (
            _normalize_required_string(
                getattr(
                    resolution,
                    "customer_id",
                    None,
                ),
                name="resolved_customer_id",
            )
        )

        if resolved_customer_id != customer_id:
            raise ValueError(
                "Customer VPS Connect customer "
                "authority does not match."
            )

        resolved_deployment_id = (
            _normalize_required_string(
                getattr(
                    resolution,
                    "deployment_id",
                    None,
                ),
                name="resolved_deployment_id",
            )
        )

        if (
            resolved_deployment_id
            != bound_deployment_id
        ):
            raise ValueError(
                "Customer VPS Connect deployment "
                "authority does not match."
            )

        agent_id = _normalize_required_string(
            getattr(
                resolution,
                "agent_id",
                None,
            ),
            name="agent_id",
        )

        resolved_account_fingerprint = (
            _normalize_required_string(
                getattr(
                    resolution,
                    "account_fingerprint",
                    None,
                ),
                name="resolved_account_fingerprint",
            )
        )

        if (
            resolved_account_fingerprint
            != normalized_account_fingerprint
        ):
            raise ValueError(
                "Customer VPS Connect account "
                "authority does not match."
            )

        return self._issue_grant(
            customer_id=customer_id,
            deployment_id=(
                bound_deployment_id
            ),
            agent_id=agent_id,
            account_fingerprint=(
                normalized_account_fingerprint
            ),
        )
