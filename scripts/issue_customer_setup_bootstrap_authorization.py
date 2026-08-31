"""
TODOBA Customer Setup Bootstrap Authorization Operator CLI.

Offline trusted-operator boundary for issuing one customer
setup bootstrap authorization.

The operator supplies:
- stable authorization request identity
- authoritative commercial customer identity
- customer-generated PKCE S256 code challenge
- explicit confirmation that TODOBA runtime is stopped

This boundary never:
- creates customer identities
- receives the PKCE code verifier
- starts or imports backend.main
- exposes an HTTP route
- owns launch-credential issuance
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from backend.config import (
    TODOBA_CONTROL_PLANE_DATA_ROOT,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_setup_bootstrap_authorization_service import (
    CustomerSetupBootstrapAuthorizationIssuance,
    CustomerSetupBootstrapAuthorizationService,
    CustomerSetupBootstrapAuthorizationStore,
)


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _compose_issuance_service(
    *,
    control_plane_root: Path,
) -> CustomerSetupBootstrapAuthorizationService:
    commercial_root = (
        Path(control_plane_root)
        / "commercial"
    )

    customer_identity_registry = (
        CustomerIdentityRegistry(
            commercial_root
            / "customer_identities.json"
        )
    )

    if not customer_identity_registry.is_ready():
        raise RuntimeError(
            "Customer identity registry is not provisioned."
        )

    authorization_store = (
        CustomerSetupBootstrapAuthorizationStore(
            commercial_root
            / (
                "customer_setup_bootstrap_"
                "authorizations.json"
            ),
            customer_identity_registry=(
                customer_identity_registry
            ),
        )
    )

    authorization_store.open_existing()

    if not authorization_store.is_ready():
        raise RuntimeError(
            "Customer setup bootstrap authorization "
            "store is not ready."
        )

    return (
        CustomerSetupBootstrapAuthorizationService(
            authorization_store=(
                authorization_store
            ),
            customer_identity_registry=(
                customer_identity_registry
            ),
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Issue one TODOBA customer setup bootstrap "
            "authorization."
        )
    )

    parser.add_argument(
        "--authorization-request-id",
        required=True,
        help=(
            "Stable operator request identity. Reuse the "
            "same value for a safe retry."
        ),
    )

    parser.add_argument(
        "--customer-id",
        required=True,
        help=(
            "Authoritative commercial customer identity."
        ),
    )

    parser.add_argument(
        "--code-challenge-s256",
        required=True,
        help=(
            "Customer-generated PKCE S256 code challenge. "
            "Never supply the code verifier here."
        ),
    )

    parser.add_argument(
        "--confirm-runtime-stopped",
        action="store_true",
        required=True,
        help=(
            "Operator confirmation that TODOBA runtime is "
            "stopped before durable authorization writes."
        ),
    )

    return parser


def _print_safe_result(
    result: CustomerSetupBootstrapAuthorizationIssuance,
) -> None:
    if not isinstance(
        result,
        CustomerSetupBootstrapAuthorizationIssuance,
    ):
        raise RuntimeError(
            "Bootstrap authorization issuance returned "
            "invalid result."
        )

    print(
        "TODOBA CUSTOMER SETUP BOOTSTRAP "
        "AUTHORIZATION ISSUED"
    )
    print(
        "SAVE AND DELIVER THE FOLLOWING "
        "AUTHORIZATION CODE SECURELY."
    )
    print(
        "Authorization code:"
    )
    print(
        result.authorization_code
    )
    print(
        "Expires at: "
        f"{result.expires_at}"
    )


def main(
    argv: Sequence[str] | None = None,
) -> None:
    parser = _build_parser()

    arguments = parser.parse_args(
        argv
    )

    if not arguments.confirm_runtime_stopped:
        raise RuntimeError(
            "TODOBA runtime must be stopped before "
            "bootstrap authorization issuance."
        )

    issuance_service = (
        _compose_issuance_service(
            control_plane_root=(
                TODOBA_CONTROL_PLANE_DATA_ROOT
            ),
        )
    )

    result = issuance_service.issue(
        authorization_request_id=(
            arguments.authorization_request_id
        ),
        customer_id=(
            arguments.customer_id
        ),
        code_challenge_s256=(
            arguments.code_challenge_s256
        ),
        current_time=_utc_now(),
    )

    _print_safe_result(
        result
    )


if __name__ == "__main__":
    main()
