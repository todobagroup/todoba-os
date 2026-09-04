"""
TODOBA Trading AI Setup real frozen acceptance journey.

Operator-assisted acceptance tooling only.

Security/order contract:

    isolated durable stores
        -> production HTTP registration
        -> runtime STOP
        -> frozen production EXE creates PKCE challenge
        -> offline authoritative bootstrap authorization
        -> production runtime START
        -> Bootstrap / Entry / Provision
        -> build_pending
        -> runtime STOP
        -> authoritative package-build processor
        -> production runtime START
        -> explicit customer Continue
        -> Continue / Package / Install
        -> customer clicks Finish
        -> frozen Setup exits

Important boundaries:
- registration is performed through the real production HTTP API
- customer_id is server-issued
- code verifier never enters this owner
- Authorization Code never enters this owner
- bootstrap authorization issuance occurs only while runtime is stopped
- package building occurs only while runtime is stopped
- customer Setup talks to the server through real localhost TCP
- deployment master key is generated in memory and passed only
  through child-process environments
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
from typing import Mapping, Sequence

import httpx

from backend.commercial.customer_access_credential_registry import (
    CustomerAccessCredentialRegistry,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecretStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_deployment_master_key import (
    decode_customer_deployment_master_key,
)
from backend.commercial.customer_registration_api import (
    _REGISTRATION_PATH,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from scripts.customer_setup_windows_acceptance import (
    launch_frozen_customer_setup,
    normalize_acceptance_base_url,
    require_production_executable,
)
from scripts.customer_setup_windows_acceptance_server import (
    build_server_environment,
    prepare_isolated_control_plane,
    start_production_server,
    stop_production_server,
    validate_loopback_port,
    wait_for_server_ready,
)


_EXPECTED_FROZEN_EXE_SHA256 = (
    "CEBFC6B659C6792B3CFC3D59C0AFE1F7"
    "CD5A2FF439254EE60F8682EB238A79E1"
)

_LOOPBACK_HOST = "127.0.0.1"

_PKCE_S256_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{43}$"
)


@dataclass(
    frozen=True,
    slots=True,
)
class FrozenCustomerSetupAcceptanceResult:
    acceptance_root: Path
    setup_base_url: str
    customer_id: str
    frozen_executable_sha256: str
    published_artifact_path: Path
    installed_artifact_path: Path
    installed_artifact_sha256: str
    installed_artifact_size_bytes: int


def _repository_root() -> Path:
    return (
        Path(__file__)
        .resolve()
        .parents[1]
    )


def _normalize_required_string(
    *,
    name: str,
    value: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be str."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{name} is required."
        )

    return normalized


def validate_pkce_s256_challenge(
    value: str,
) -> str:
    normalized = (
        _normalize_required_string(
            name="code_challenge_s256",
            value=value,
        )
    )

    if (
        _PKCE_S256_PATTERN
        .fullmatch(
            normalized
        )
        is None
    ):
        raise ValueError(
            "code_challenge_s256 "
            "must be a PKCE S256 challenge."
        )

    return normalized


def generate_encoded_master_key() -> str:
    """
    Generate one in-memory AES-256 master key representation.
    """

    raw_key = secrets.token_bytes(
        32
    )

    if len(
        raw_key
    ) != 32:
        raise RuntimeError(
            "Generated deployment master key "
            "has invalid length."
        )

    return (
        base64.urlsafe_b64encode(
            raw_key
        )
        .decode(
            "ascii"
        )
    )


def select_loopback_port() -> int:
    """
    Ask Windows for one currently-free IPv4 loopback port.
    """

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as probe:
        probe.bind(
            (
                _LOOPBACK_HOST,
                0,
            )
        )

        port = int(
            probe.getsockname()[
                1
            ]
        )

    return validate_loopback_port(
        port
    )


def prepare_acceptance_root(
    acceptance_root: Path,
) -> tuple[
    Path,
    Path,
    Path,
]:
    if not isinstance(
        acceptance_root,
        Path,
    ):
        raise TypeError(
            "acceptance_root must be Path."
        )

    resolved = acceptance_root.resolve()

    repository_root = (
        _repository_root()
        .resolve()
    )

    if (
        resolved == repository_root
        or repository_root
        in resolved.parents
    ):
        raise ValueError(
            "acceptance_root must be outside "
            "the repository."
        )

    if resolved.exists():
        if not resolved.is_dir():
            raise ValueError(
                "acceptance_root must be a directory."
            )

        if any(
            resolved.iterdir()
        ):
            raise RuntimeError(
                "acceptance_root must be empty."
            )
    else:
        resolved.mkdir(
            parents=True,
            exist_ok=False,
        )

    control_plane_root = (
        resolved
        / "control-plane"
    )

    package_root = (
        resolved
        / "packages"
    )

    workspace_root = (
        resolved
        / "package-build-workspace"
    )

    workspace_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    return (
        control_plane_root,
        package_root,
        workspace_root,
    )


def _initialize_if_missing(
    owner,
) -> None:
    """
    Explicit acceptance-only initialization boundary.

    Production runtime remains fail-closed. This helper
    may only prepare missing empty durable substrate.
    """

    if not owner.is_ready():
        owner.initialize_empty()


def prepare_authoritative_identity_substrate(
    *,
    control_plane_root: Path,
) -> Path:
    """
    Create only the empty durable CustomerIdentityRegistry
    substrate required before Setup control-plane provisioning.

    Customer creation remains exclusively owned by the
    production customer registration HTTP boundary.
    """

    if not isinstance(
        control_plane_root,
        Path,
    ):
        raise TypeError(
            "control_plane_root must be Path."
        )

    resolved_control_plane_root = (
        control_plane_root.resolve()
    )

    repository_root = (
        _repository_root()
        .resolve()
    )

    if (
        resolved_control_plane_root
        == repository_root
        or repository_root
        in resolved_control_plane_root.parents
    ):
        raise ValueError(
            "control_plane_root must be outside "
            "the repository."
        )

    identity_path = (
        resolved_control_plane_root
        / "commercial"
        / "customer_identities.json"
    )

    registry = CustomerIdentityRegistry(
        identity_path
    )

    _initialize_if_missing(
        registry
    )

    if not registry.is_ready():
        raise RuntimeError(
            "Customer identity registry substrate "
            "did not become ready."
        )

    if registry.size() != 0:
        raise RuntimeError(
            "Acceptance identity substrate must "
            "start empty."
        )

    return identity_path


def prepare_authoritative_runtime_substrate(
    *,
    control_plane_root: Path,
    encoded_master_key: str,
) -> dict[
    str,
    Path,
]:
    """
    Prepare every empty durable owner required for the real
    production backend to start against a fresh acceptance root.

    This is substrate initialization only.

    It does not:
    - register a customer
    - issue customer access credentials
    - create a deployment
    - write deployment secrets
    - activate an entitlement
    - bind an MT5 account
    """

    if not isinstance(
        control_plane_root,
        Path,
    ):
        raise TypeError(
            "control_plane_root must be Path."
        )

    normalized_master_key = (
        _normalize_required_string(
            name="encoded_master_key",
            value=encoded_master_key,
        )
    )

    resolved_control_plane_root = (
        control_plane_root.resolve()
    )

    repository_root = (
        _repository_root()
        .resolve()
    )

    if (
        resolved_control_plane_root
        == repository_root
        or repository_root
        in resolved_control_plane_root.parents
    ):
        raise ValueError(
            "control_plane_root must be outside "
            "the repository."
        )

    commercial_root = (
        resolved_control_plane_root
        / "commercial"
    )

    trading_root = (
        resolved_control_plane_root
        / "trading"
    )

    deployment_registry = (
        CustomerDeploymentRegistry(
            commercial_root
            / "customer_deployments.json"
        )
    )

    _initialize_if_missing(
        deployment_registry
    )

    master_key = (
        decode_customer_deployment_master_key(
            normalized_master_key
        )
    )

    secret_store = (
        CustomerDeploymentSecretStore(
            commercial_root
            / "customer_deployment_secrets.json",
            master_key=master_key,
        )
    )

    _initialize_if_missing(
        secret_store
    )

    identity_path = (
        prepare_authoritative_identity_substrate(
            control_plane_root=(
                resolved_control_plane_root
            )
        )
    )

    identity_registry = (
        CustomerIdentityRegistry(
            identity_path
        )
    )

    if not identity_registry.is_ready():
        raise RuntimeError(
            "Customer identity registry substrate "
            "did not reopen ready."
        )

    access_credential_registry = (
        CustomerAccessCredentialRegistry(
            commercial_root
            / "customer_access_credentials.json",
            customer_identity_registry=(
                identity_registry
            ),
        )
    )

    _initialize_if_missing(
        access_credential_registry
    )

    entitlement_registry = (
        CustomerDeploymentEntitlementRegistry(
            commercial_root
            / "customer_deployment_entitlements.json",
            deployment_registry=(
                deployment_registry
            ),
        )
    )

    _initialize_if_missing(
        entitlement_registry
    )

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            trading_root
            / "trusted_agent_account_bindings.json"
        )
    )

    _initialize_if_missing(
        account_binding_store
    )

    owners = (
        (
            "customer deployment registry",
            deployment_registry,
        ),
        (
            "customer deployment secret store",
            secret_store,
        ),
        (
            "customer identity registry",
            identity_registry,
        ),
        (
            "customer access credential registry",
            access_credential_registry,
        ),
        (
            "customer deployment entitlement registry",
            entitlement_registry,
        ),
        (
            "trusted-agent account binding store",
            account_binding_store,
        ),
    )

    for owner_name, owner in owners:
        if not owner.is_ready():
            raise RuntimeError(
                f"{owner_name} did not become ready."
            )

        if owner.size() != 0:
            raise RuntimeError(
                f"{owner_name} must start empty."
            )

    return {
        "deployment_registry": (
            commercial_root
            / "customer_deployments.json"
        ),
        "deployment_secret_store": (
            commercial_root
            / "customer_deployment_secrets.json"
        ),
        "identity_registry": (
            identity_path
        ),
        "access_credential_registry": (
            commercial_root
            / "customer_access_credentials.json"
        ),
        "entitlement_registry": (
            commercial_root
            / "customer_deployment_entitlements.json"
        ),
        "account_binding_store": (
            trading_root
            / "trusted_agent_account_bindings.json"
        ),
    }


def require_build_inputs(
    *,
    platform_mql5_root: Path,
    metaeditor_path: Path,
) -> tuple[
    Path,
    Path,
]:
    if not isinstance(
        platform_mql5_root,
        Path,
    ):
        raise TypeError(
            "platform_mql5_root must be Path."
        )

    if not isinstance(
        metaeditor_path,
        Path,
    ):
        raise TypeError(
            "metaeditor_path must be Path."
        )

    resolved_mql5_root = (
        platform_mql5_root
        .resolve()
    )

    resolved_metaeditor = (
        metaeditor_path
        .resolve()
    )

    if not resolved_mql5_root.is_dir():
        raise RuntimeError(
            "platform_mql5_root "
            "is not available."
        )

    if not resolved_metaeditor.is_file():
        raise RuntimeError(
            "metaeditor_path "
            "is not available."
        )

    if (
        resolved_metaeditor.suffix.lower()
        != ".exe"
    ):
        raise RuntimeError(
            "metaeditor_path must point "
            "to a Windows executable."
        )

    return (
        resolved_mql5_root,
        resolved_metaeditor,
    )


def require_locked_frozen_executable(
) -> tuple[
    Path,
    str,
]:
    executable = (
        require_production_executable()
    )

    digest = hashlib.sha256(
        executable.read_bytes()
    ).hexdigest().upper()

    if (
        digest
        != _EXPECTED_FROZEN_EXE_SHA256
    ):
        raise RuntimeError(
            "Frozen production Setup "
            "executable hash changed."
        )

    return (
        executable,
        digest,
    )


def verify_frozen_installation(
    *,
    platform_mql5_root: Path,
    package_root: Path,
) -> tuple[
    Path,
    Path,
    str,
    int,
]:
    """
    Prove the final customer-side EX5 exactly matches the
    authoritative package produced by this isolated run.
    """

    if not isinstance(
        platform_mql5_root,
        Path,
    ):
        raise TypeError(
            "platform_mql5_root must be Path."
        )

    if not isinstance(
        package_root,
        Path,
    ):
        raise TypeError(
            "package_root must be Path."
        )

    resolved_mql5_root = (
        platform_mql5_root.resolve()
    )

    resolved_package_root = (
        package_root.resolve()
    )

    if not resolved_mql5_root.is_dir():
        raise RuntimeError(
            "platform_mql5_root is not available "
            "for installation verification."
        )

    if not resolved_package_root.is_dir():
        raise RuntimeError(
            "package_root is not available "
            "for installation verification."
        )

    published_candidates = tuple(
        sorted(
            (
                candidate.resolve()
                for candidate
                in resolved_package_root.rglob(
                    "*.ex5"
                )
                if candidate.is_file()
            ),
            key=lambda candidate: str(
                candidate
            ).lower(),
        )
    )

    if len(
        published_candidates
    ) != 1:
        raise RuntimeError(
            "Acceptance package root must contain "
            "exactly one published EX5."
        )

    published_artifact = (
        published_candidates[
            0
        ]
    )

    installed_artifact = (
        resolved_mql5_root
        / "Experts"
        / published_artifact.name
    )

    if not installed_artifact.is_file():
        raise RuntimeError(
            "Frozen Setup did not leave the "
            "published EX5 installed."
        )

    published_size = (
        published_artifact
        .stat()
        .st_size
    )

    installed_size = (
        installed_artifact
        .stat()
        .st_size
    )

    if published_size <= 0:
        raise RuntimeError(
            "Published acceptance EX5 is empty."
        )

    if (
        installed_size
        != published_size
    ):
        raise RuntimeError(
            "Installed EX5 size does not match "
            "the published package."
        )

    published_sha256 = (
        hashlib.sha256(
            published_artifact
            .read_bytes()
        )
        .hexdigest()
        .upper()
    )

    installed_sha256 = (
        hashlib.sha256(
            installed_artifact
            .read_bytes()
        )
        .hexdigest()
        .upper()
    )

    if (
        installed_sha256
        != published_sha256
    ):
        raise RuntimeError(
            "Installed EX5 SHA-256 does not match "
            "the published package."
        )

    return (
        published_artifact,
        installed_artifact,
        installed_sha256,
        installed_size,
    )


def register_customer_over_production_http(
    *,
    setup_base_url: str,
    registration_request_id: str,
    timeout_seconds: float = 10.0,
) -> str:
    base_url = (
        normalize_acceptance_base_url(
            setup_base_url
        )
    )

    normalized_request_id = (
        _normalize_required_string(
            name="registration_request_id",
            value=registration_request_id,
        )
    )

    if not isinstance(
        timeout_seconds,
        (
            int,
            float,
        ),
    ):
        raise TypeError(
            "timeout_seconds must be numeric."
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be positive."
        )

    response = httpx.post(
        (
            f"{base_url}"
            f"{_REGISTRATION_PATH}"
        ),
        json={
            "registration_request_id": (
                normalized_request_id
            ),
        },
        timeout=float(
            timeout_seconds
        ),
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Customer registration response "
            "must be an object."
        )

    expected_keys = {
        "registration_request_id",
        "customer_id",
    }

    if set(
        payload
    ) != expected_keys:
        raise RuntimeError(
            "Customer registration response "
            "shape changed."
        )

    if (
        payload[
            "registration_request_id"
        ]
        != normalized_request_id
    ):
        raise RuntimeError(
            "Customer registration request "
            "identity mismatch."
        )

    customer_id = (
        payload[
            "customer_id"
        ]
    )

    return (
        _normalize_required_string(
            name="customer_id",
            value=customer_id,
        )
    )


def issue_bootstrap_authorization(
    *,
    customer_id: str,
    authorization_request_id: str,
    code_challenge_s256: str,
    environment: Mapping[
        str,
        str,
    ],
) -> None:
    normalized_customer_id = (
        _normalize_required_string(
            name="customer_id",
            value=customer_id,
        )
    )

    normalized_request_id = (
        _normalize_required_string(
            name="authorization_request_id",
            value=authorization_request_id,
        )
    )

    normalized_challenge = (
        validate_pkce_s256_challenge(
            code_challenge_s256
        )
    )

    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment must be Mapping."
        )

    command = [
        sys.executable,
        "-m",
        (
            "scripts."
            "issue_customer_setup_bootstrap_authorization"
        ),
        "--authorization-request-id",
        normalized_request_id,
        "--customer-id",
        normalized_customer_id,
        "--code-challenge-s256",
        normalized_challenge,
        "--confirm-runtime-stopped",
    ]

    subprocess.run(
        command,
        cwd=_repository_root(),
        env=dict(
            environment
        ),
        shell=False,
        check=True,
    )


def process_package_build_requests(
    *,
    platform_mql5_root: Path,
    metaeditor_path: Path,
    workspace_root: Path,
    environment: Mapping[
        str,
        str,
    ],
) -> None:
    (
        resolved_mql5_root,
        resolved_metaeditor,
    ) = require_build_inputs(
        platform_mql5_root=(
            platform_mql5_root
        ),
        metaeditor_path=(
            metaeditor_path
        ),
    )

    if not isinstance(
        workspace_root,
        Path,
    ):
        raise TypeError(
            "workspace_root must be Path."
        )

    resolved_workspace = (
        workspace_root.resolve()
    )

    repository_root = (
        _repository_root()
        .resolve()
    )

    if (
        resolved_workspace
        == repository_root
        or repository_root
        in resolved_workspace.parents
    ):
        raise ValueError(
            "workspace_root must be "
            "outside the repository."
        )

    resolved_workspace.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment must be Mapping."
        )

    command = [
        sys.executable,
        "-m",
        (
            "scripts."
            "process_customer_deployment_package_build_requests"
        ),
        "--platform-mql5-root",
        str(
            resolved_mql5_root
        ),
        "--metaeditor-path",
        str(
            resolved_metaeditor
        ),
        "--workspace-root",
        str(
            resolved_workspace
        ),
    ]

    subprocess.run(
        command,
        cwd=_repository_root(),
        env=dict(
            environment
        ),
        shell=False,
        check=True,
    )


def _require_process_alive(
    *,
    process: subprocess.Popen,
    name: str,
) -> None:
    if not isinstance(
        process,
        subprocess.Popen,
    ):
        raise TypeError(
            f"{name} must be subprocess.Popen."
        )

    return_code = process.poll()

    if return_code is not None:
        raise RuntimeError(
            f"{name} exited unexpectedly "
            f"with code {return_code}."
        )


def _wait_for_process_exit(
    *,
    process: subprocess.Popen,
    name: str,
    timeout_seconds: float = 5.0,
) -> int:
    """
    Allow a bounded grace period for a process that the
    operator has already closed through its normal UI.

    This helper never terminates or kills the process.
    """

    if not isinstance(
        process,
        subprocess.Popen,
    ):
        raise TypeError(
            f"{name} must be subprocess.Popen."
        )

    if not isinstance(
        timeout_seconds,
        (
            int,
            float,
        ),
    ):
        raise TypeError(
            "timeout_seconds must be numeric."
        )

    normalized_timeout = float(
        timeout_seconds
    )

    if normalized_timeout <= 0.0:
        raise ValueError(
            "timeout_seconds must be positive."
        )

    try:
        return_code = process.wait(
            timeout=normalized_timeout
        )

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{name} did not exit within "
            f"{normalized_timeout:.1f} seconds "
            f"after its window was closed."
        ) from exc

    if return_code is None:
        raise RuntimeError(
            f"{name} returned no exit code."
        )

    return int(
        return_code
    )


def run_operator_assisted_frozen_journey(
    *,
    acceptance_root: Path,
    registration_request_id: str,
    authorization_request_id: str,
    platform_mql5_root: Path,
    metaeditor_path: Path,
    port: int | None = None,
) -> FrozenCustomerSetupAcceptanceResult:
    """
    Run one isolated real frozen acceptance journey.

    Human interaction is intentionally retained for:
    - copying the PKCE challenge from the frozen GUI
    - entering the separately-issued Authorization Code
      into the frozen GUI
    - acknowledging build_pending before package building
    - clicking the explicit Continue action
    - clicking Finish and observing the frozen Setup close
    """

    (
        resolved_mql5_root,
        resolved_metaeditor,
    ) = require_build_inputs(
        platform_mql5_root=(
            platform_mql5_root
        ),
        metaeditor_path=(
            metaeditor_path
        ),
    )

    (
        executable,
        executable_sha256,
    ) = (
        require_locked_frozen_executable()
    )

    (
        control_plane_root,
        package_root,
        workspace_root,
    ) = prepare_acceptance_root(
        acceptance_root
    )

    encoded_master_key = (
        generate_encoded_master_key()
    )

    prepare_authoritative_runtime_substrate(
        control_plane_root=(
            control_plane_root
        ),
        encoded_master_key=(
            encoded_master_key
        ),
    )

    prepare_isolated_control_plane(
        control_plane_root=(
            control_plane_root
        ),
        package_root=(
            package_root
        ),
    )

    server_environment = (
        build_server_environment(
            control_plane_root=(
                control_plane_root
            ),
            package_root=(
                package_root
            ),
            encoded_master_key=(
                encoded_master_key
            ),
            parent_environment=(
                os.environ
            ),
        )
    )

    if port is None:
        selected_port = (
            select_loopback_port()
        )
    else:
        selected_port = (
            validate_loopback_port(
                port
            )
        )

    setup_base_url = (
        normalize_acceptance_base_url(
            f"http://"
            f"{_LOOPBACK_HOST}:"
            f"{selected_port}"
        )
    )

    server_process = None
    setup_process = None

    try:
        # ====================================================
        # PHASE 1 ? PRODUCTION HTTP REGISTRATION
        # ====================================================

        print(
            "\n===== G2B2 PHASE 1 ? "
            "PRODUCTION REGISTRATION ====="
        )

        server_process = (
            start_production_server(
                port=selected_port,
                environment=(
                    server_environment
                ),
            )
        )

        wait_for_server_ready(
            process=server_process,
            port=selected_port,
        )

        customer_id = (
            register_customer_over_production_http(
                setup_base_url=(
                    setup_base_url
                ),
                registration_request_id=(
                    registration_request_id
                ),
            )
        )

        print(
            "PASS: customer registered "
            "through production HTTP."
        )

        print(
            f"CUSTOMER_ID={customer_id}"
        )

        # Runtime MUST stop before bootstrap authorization.
        stop_production_server(
            process=server_process
        )

        server_process = None

        # ====================================================
        # PHASE 2 ? FROZEN EXE CREATES PKCE CHALLENGE
        # ====================================================

        print(
            "\n===== G2B2 PHASE 2 ? "
            "FROZEN PKCE CHALLENGE ====="
        )

        setup_process = (
            launch_frozen_customer_setup(
                setup_base_url=(
                    setup_base_url
                ),
                executable_path=(
                    executable
                ),
            )
        )

        _require_process_alive(
            process=setup_process,
            name="Frozen customer Setup",
        )

        print(
            "The real TODOBA Trading AI Setup "
            "window is now running."
        )

        print(
            "Copy the PKCE S256 challenge shown "
            "by the frozen Setup window."
        )

        code_challenge_s256 = (
            validate_pkce_s256_challenge(
                input(
                    "Paste PKCE challenge here: "
                )
            )
        )

        # ====================================================
        # PHASE 3 ? OFFLINE AUTHORIZATION WHILE STOPPED
        # ====================================================

        print(
            "\n===== G2B2 PHASE 3 ? "
            "BOOTSTRAP AUTHORIZATION ====="
        )

        issue_bootstrap_authorization(
            customer_id=customer_id,
            authorization_request_id=(
                authorization_request_id
            ),
            code_challenge_s256=(
                code_challenge_s256
            ),
            environment=(
                server_environment
            ),
        )

        print(
            "\nThe authoritative issuance command "
            "printed the Authorization Code above."
        )

        print(
            "Do NOT paste that code into this console."
        )

        # ====================================================
        # PHASE 4 ? REAL BOOTSTRAP / ENTRY / PROVISION
        # ====================================================

        print(
            "\n===== G2B2 PHASE 4 ? "
            "REAL FROZEN SETUP JOURNEY ====="
        )

        server_process = (
            start_production_server(
                port=selected_port,
                environment=(
                    server_environment
                ),
            )
        )

        wait_for_server_ready(
            process=server_process,
            port=selected_port,
        )

        _require_process_alive(
            process=setup_process,
            name="Frozen customer Setup",
        )

        print(
            "Paste the Authorization Code into "
            "the frozen Setup window and Continue."
        )

        print(
            "Wait until Setup reports that the "
            "package build is pending."
        )

        input(
            "When BUILD_PENDING is visible, "
            "press Enter here: "
        )

        _require_process_alive(
            process=setup_process,
            name="Frozen customer Setup",
        )

        # Package build is intentionally performed with the
        # production HTTP runtime stopped.
        stop_production_server(
            process=server_process
        )

        server_process = None

        # ====================================================
        # PHASE 5 ? AUTHORITATIVE PACKAGE BUILD
        # ====================================================

        print(
            "\n===== G2B2 PHASE 5 ? "
            "PACKAGE BUILD ====="
        )

        process_package_build_requests(
            platform_mql5_root=(
                resolved_mql5_root
            ),
            metaeditor_path=(
                resolved_metaeditor
            ),
            workspace_root=(
                workspace_root
            ),
            environment=(
                server_environment
            ),
        )

        print(
            "PASS: authoritative package-build "
            "processor completed."
        )

        # ====================================================
        # PHASE 6 ? EXPLICIT CONTINUE / INSTALL / FINISH
        # ====================================================

        print(
            "\n===== G2B2 PHASE 6 ? "
            "EXPLICIT CONTINUE + INSTALL + FINISH ====="
        )

        server_process = (
            start_production_server(
                port=selected_port,
                environment=(
                    server_environment
                ),
            )
        )

        wait_for_server_ready(
            process=server_process,
            port=selected_port,
        )

        _require_process_alive(
            process=setup_process,
            name="Frozen customer Setup",
        )

        print(
            'Click the explicit Continue action in the frozen Setup.'
        )

        print(
            "Complete the customer-visible Setup flow."
        )

        print(
            'When Finish is enabled, click Finish and wait for the TODOBA Trading AI Setup window to close.'
        )

        input(
            'After you click Finish and the frozen Setup window closes, press Enter here: '
        )

        _wait_for_process_exit(
            process=setup_process,
            name="Frozen customer Setup",
            timeout_seconds=5.0,
        )

        stop_production_server(
            process=server_process
        )

        server_process = None

        (
            published_artifact_path,
            installed_artifact_path,
            installed_artifact_sha256,
            installed_artifact_size_bytes,
        ) = verify_frozen_installation(
            platform_mql5_root=(
                resolved_mql5_root
            ),
            package_root=(
                package_root
            ),
        )

        print(
            "\nPASS: real frozen Setup process "
            "completed and closed."
        )

        print(
            "PASS: installed EX5 exactly matches "
            "the authoritative published package."
        )

        print(
            f"PUBLISHED_EX5="
            f"{published_artifact_path}"
        )

        print(
            f"INSTALLED_EX5="
            f"{installed_artifact_path}"
        )

        print(
            f"INSTALLED_EX5_SHA256="
            f"{installed_artifact_sha256}"
        )

        print(
            f"INSTALLED_EX5_SIZE="
            f"{installed_artifact_size_bytes}"
        )

        return (
            FrozenCustomerSetupAcceptanceResult(
                acceptance_root=(
                    acceptance_root.resolve()
                ),
                setup_base_url=(
                    setup_base_url
                ),
                customer_id=(
                    customer_id
                ),
                frozen_executable_sha256=(
                    executable_sha256
                ),
                published_artifact_path=(
                    published_artifact_path
                ),
                installed_artifact_path=(
                    installed_artifact_path
                ),
                installed_artifact_sha256=(
                    installed_artifact_sha256
                ),
                installed_artifact_size_bytes=(
                    installed_artifact_size_bytes
                ),
            )
        )

    finally:
        if server_process is not None:
            try:
                stop_production_server(
                    process=server_process
                )
            except Exception:
                pass



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run one isolated operator-assisted real "
            "TODOBA Trading AI Setup frozen journey."
        )
    )

    parser.add_argument(
        "--acceptance-root",
        required=True,
        type=Path,
        help=(
            "Empty external directory reserved for this "
            "acceptance run."
        ),
    )

    parser.add_argument(
        "--registration-request-id",
        required=True,
        help=(
            "Stable idempotency identity for the "
            "production customer registration request."
        ),
    )

    parser.add_argument(
        "--authorization-request-id",
        required=True,
        help=(
            "Stable operator request identity for "
            "bootstrap authorization issuance."
        ),
    )

    parser.add_argument(
        "--platform-mql5-root",
        required=True,
        type=Path,
        help=(
            "MQL5 root of the installed MetaTrader platform "
            "used for authoritative package compilation."
        ),
    )

    parser.add_argument(
        "--metaeditor-path",
        required=True,
        type=Path,
        help=(
            "Exact MetaEditor Windows executable used "
            "for package compilation."
        ),
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            "Optional explicit localhost port. "
            "Default: choose one currently-free port."
        ),
    )

    return parser


def main(
    argv: Sequence[
        str
    ] | None = None,
) -> int:
    parser = _build_parser()

    arguments = (
        parser.parse_args(
            argv
        )
    )

    result = (
        run_operator_assisted_frozen_journey(
            acceptance_root=(
                arguments.acceptance_root
            ),
            registration_request_id=(
                arguments.registration_request_id
            ),
            authorization_request_id=(
                arguments.authorization_request_id
            ),
            platform_mql5_root=(
                arguments.platform_mql5_root
            ),
            metaeditor_path=(
                arguments.metaeditor_path
            ),
            port=arguments.port,
        )
    )

    print(
        "\n===== G2B2 REAL FROZEN "
        "JOURNEY COMPLETED ====="
    )

    print(
        f"ACCEPTANCE_ROOT="
        f"{result.acceptance_root}"
    )

    print(
        f"SETUP_BASE_URL="
        f"{result.setup_base_url}"
    )

    print(
        f"CUSTOMER_ID="
        f"{result.customer_id}"
    )

    print(
        f"FROZEN_EXE_SHA256="
        f"{result.frozen_executable_sha256}"
    )

    print(
        f"PUBLISHED_EX5="
        f"{result.published_artifact_path}"
    )

    print(
        f"INSTALLED_EX5="
        f"{result.installed_artifact_path}"
    )

    print(
        f"INSTALLED_EX5_SHA256="
        f"{result.installed_artifact_sha256}"
    )

    print(
        f"INSTALLED_EX5_SIZE="
        f"{result.installed_artifact_size_bytes}"
    )

    print(
        "PASS: G2B2 operator-assisted "
        "real frozen journey completed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
