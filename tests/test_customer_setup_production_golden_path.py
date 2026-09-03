"""
TODOBA Production Customer Setup Golden Path

Proof for the continuation-capable production composition:

    authoritative customer/setup state
        -> production Setup composition
        -> CustomerSetupHttpClient
        -> POST /customer/setup/provision
        -> 202 build_pending + real continuation credential
        -> external package build completion
        -> explicit customer retry
        -> POST /customer/setup/continue
        -> deployment activation + entitlement + setup bind
        -> GET /customer/setup/package
        -> exact EX5 bytes
        -> CustomerSetupOrchestrationService
        -> installer boundary
        -> installed

The test keeps commercial/security authorities real.

Only two external effects are simulated:
- asynchronous package build completion
- physical MT5 EX5 filesystem installation

All durable state is isolated beneath tmp_path.
No real network, MetaEditor, MT5 process, or production data is used.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import hashlib
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import main
from backend.commercial.customer_deployment_authorizer import (
    CustomerDeploymentAuthorizer,
)
from backend.commercial.customer_deployment_entitlement_authorizer import (
    CustomerDeploymentEntitlementAuthorizer,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_package_publication import (
    CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME,
    CustomerDeploymentPackagePublication,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_deployment_runtime_projection import (
    CustomerDeploymentRuntimeProjection,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecretStore,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentity,
    CustomerIdentityRegistry,
)
from backend.commercial.customer_mt5_ex5_installer_service import (
    CustomerMT5EX5InstallationResult,
    CustomerMT5EX5InstallerService,
)
from backend.commercial.customer_mt5_setup_preflight_service import (
    CustomerMT5SetupPreflightResult,
)
from backend.commercial.customer_setup_http_client import (
    CustomerSetupHttpClient,
)
from backend.commercial.customer_setup_orchestration_service import (
    CustomerSetupOrchestrationService,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTargetRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)
from scripts.provision_customer_setup_control_plane import (
    provision_customer_setup_control_plane,
)


CUSTOMER_ID = "customer-golden-path-001"

LOGIN = 12345678
SERVER = "Broker-Server"

ACCOUNT_FINGERPRINT = (
    f"{SERVER}:{LOGIN}"
)

SETUP_BASE_URL = (
    "https://api.todobagroup.com"
)

ARTIFACT_BYTES = (
    b"TODOBA-PRODUCTION-GOLDEN-PATH-EX5"
)

ARTIFACT_SHA256 = hashlib.sha256(
    ARTIFACT_BYTES
).hexdigest()

ARTIFACT_SIZE_BYTES = len(
    ARTIFACT_BYTES
)

MASTER_KEY = b"G" * 32


_RUNTIME_EXPORT_NAMES = (
    "customer_registration_store",
    "customer_setup_launch_credential_store",
    "customer_setup_bootstrap_authorization_store",
    "customer_setup_activation_store",
    "customer_setup_handoff_store",
    "customer_setup_build_continuation_store",
    "customer_deployment_bootstrap_store",
    "customer_deployment_package_build_request_store",
    "customer_registration_service",
    "customer_setup_launch_credential_service",
    "customer_setup_bootstrap_authorization_service",
    "customer_setup_bootstrap_launch_grant_service",
    "customer_setup_entry_grant_service",
    "customer_setup_activation_service",
    "customer_setup_handoff_service",
    "customer_setup_handoff_authorizer",
    "customer_setup_build_continuation_service",
    "customer_deployment_enrollment_service",
    "customer_deployment_bootstrap_service",
)


def _build_preflight(
    tmp_path: Path,
) -> CustomerMT5SetupPreflightResult:
    installation_path = (
        tmp_path
        / "MT5"
    )

    installation_path.mkdir()

    terminal_path = (
        installation_path
        / "terminal64.exe"
    )

    terminal_path.write_bytes(
        b"golden-path-terminal"
    )

    data_path = (
        tmp_path
        / "MT5Data"
    )

    data_path.mkdir()

    return CustomerMT5SetupPreflightResult(
        terminal_path=str(
            terminal_path.resolve()
        ),
        installation_path=str(
            installation_path.resolve()
        ),
        data_path=str(
            data_path.resolve()
        ),
        portable=False,
        login=LOGIN,
        server=SERVER,
        margin_mode=2,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )


def _authorization_header(
    headers: dict,
) -> str | None:
    for key, value in headers.items():
        if key.lower() == "authorization":
            return value

    return None


def test_production_continuation_golden_path_reaches_installed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    control_plane_root = (
        tmp_path
        / "control-plane"
    )

    commercial_root = (
        control_plane_root
        / "commercial"
    )

    package_root = (
        tmp_path
        / "customer-packages"
    )

    # ========================================================
    # AUTHORITATIVE CUSTOMER IDENTITY
    # ========================================================

    identity_registry = (
        CustomerIdentityRegistry(
            commercial_root
            / "customer_identities.json"
        )
    )

    identity_registry.initialize_empty()

    identity_registry.register(
        CustomerIdentity(
            customer_id=CUSTOMER_ID
        )
    )

    # ========================================================
    # OFFLINE PROVISION THE SETUP CONTROL PLANE
    #
    # Runtime composition must only reopen these stores.
    # It must never initialize them.
    # ========================================================

    provision_customer_setup_control_plane(
        control_plane_root=(
            control_plane_root
        ),
        confirm_runtime_stopped=True,
    )

    # ========================================================
    # REAL DEPLOYMENT SECURITY / RUNTIME OWNERS
    # ========================================================

    deployment_registry = (
        CustomerDeploymentRegistry(
            commercial_root
            / "customer_deployments.json"
        )
    )

    deployment_registry.initialize_empty()

    secret_store = (
        CustomerDeploymentSecretStore(
            commercial_root
            / "customer_deployment_secrets.json",
            master_key=MASTER_KEY,
        )
    )

    secret_store.initialize_empty()

    account_binding_store = (
        TrustedAgentAccountBindingStore(
            control_plane_root
            / "trading"
            / "trusted_agent_account_bindings.json"
        )
    )

    account_binding_store.initialize_empty()

    credential_registry = (
        TrustedAgentCredentialRegistry()
    )

    execution_signing_key_registry = (
        TrustedAgentSigningKeyRegistry()
    )

    control_signing_key_registry = (
        TrustedAgentSigningKeyRegistry()
    )

    execution_target_registry = (
        ExecutionTargetRegistry()
    )

    runtime_projection = (
        CustomerDeploymentRuntimeProjection(
            deployment_registry=(
                deployment_registry
            ),
            secret_store=secret_store,
            account_binding_store=(
                account_binding_store
            ),
            credential_registry=(
                credential_registry
            ),
            execution_signing_key_registry=(
                execution_signing_key_registry
            ),
            control_signing_key_registry=(
                control_signing_key_registry
            ),
            execution_target_registry=(
                execution_target_registry
            ),
        )
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

    entitlement_registry.initialize_empty()

    deployment_authorizer = (
        CustomerDeploymentAuthorizer(
            deployment_registry=(
                deployment_registry
            )
        )
    )

    entitlement_authorizer = (
        CustomerDeploymentEntitlementAuthorizer(
            entitlement_registry=(
                entitlement_registry
            )
        )
    )

    publication = (
        CustomerDeploymentPackagePublication(
            package_root=package_root
        )
    )

    # ========================================================
    # MAKE PRODUCTION COMPOSITION USE THIS ISOLATED REAL GRAPH
    # ========================================================

    path_overrides = {
        "CUSTOMER_REGISTRATION_STORAGE_PATH": (
            commercial_root
            / "customer_registrations.json"
        ),
        "CUSTOMER_SETUP_LAUNCH_CREDENTIAL_STORAGE_PATH": (
            commercial_root
            / "customer_setup_launch_credentials.json"
        ),
        "CUSTOMER_SETUP_BOOTSTRAP_AUTHORIZATION_STORAGE_PATH": (
            commercial_root
            / "customer_setup_bootstrap_authorizations.json"
        ),
        "CUSTOMER_SETUP_ACTIVATION_STORAGE_PATH": (
            commercial_root
            / "customer_setup_activations.json"
        ),
        "CUSTOMER_SETUP_HANDOFF_STORAGE_PATH": (
            commercial_root
            / "customer_setup_handoffs.json"
        ),
        "CUSTOMER_SETUP_BUILD_CONTINUATION_STORAGE_PATH": (
            commercial_root
            / "customer_setup_build_continuations.json"
        ),
        "CUSTOMER_DEPLOYMENT_BOOTSTRAP_STORAGE_PATH": (
            commercial_root
            / "customer_deployment_bootstraps.json"
        ),
        "CUSTOMER_DEPLOYMENT_PACKAGE_BUILD_REQUEST_STORAGE_ROOT": (
            commercial_root
            / "customer_deployment_package_build_requests"
        ),
    }

    for name, value in (
        path_overrides.items()
    ):
        monkeypatch.setattr(
            main,
            name,
            value,
        )

    source_owner_overrides = {
        "customer_identity_registry": (
            identity_registry
        ),
        "customer_deployment_registry": (
            deployment_registry
        ),
        "customer_deployment_secret_store": (
            secret_store
        ),
        "trusted_agent_account_binding_store": (
            account_binding_store
        ),
        "trusted_agent_credential_registry": (
            credential_registry
        ),
        "execution_signing_key_registry": (
            execution_signing_key_registry
        ),
        "control_signing_key_registry": (
            control_signing_key_registry
        ),
        "execution_target_registry": (
            execution_target_registry
        ),
        "customer_deployment_runtime_projection": (
            runtime_projection
        ),
        "customer_deployment_authorizer": (
            deployment_authorizer
        ),
        "customer_deployment_entitlement_registry": (
            entitlement_registry
        ),
        "customer_deployment_entitlement_authorizer": (
            entitlement_authorizer
        ),
        "customer_deployment_package_publication": (
            publication
        ),
    }

    for name, value in (
        source_owner_overrides.items()
    ):
        monkeypatch.setattr(
            main,
            name,
            value,
        )

    # Record all mutable runtime exports with monkeypatch so
    # pytest restores backend.main after this test.
    for name in _RUNTIME_EXPORT_NAMES:
        monkeypatch.setattr(
            main,
            name,
            getattr(
                main,
                name,
            ),
        )

    monkeypatch.setattr(
        main,
        "_customer_setup_runtime_composed",
        False,
    )

    app = FastAPI()

    main._compose_customer_setup_runtime(
        app
    )

    assert (
        main._customer_setup_runtime_composed
        is True
    )

    # ========================================================
    # CREATE REAL ACTIVE SETUP RIGHT + REAL HANDOFF CREDENTIAL
    #
    # This represents the already-authorized Setup entry
    # boundary immediately before account provisioning.
    # ========================================================

    activation = (
        main.customer_setup_activation_service
        .activate(
            activation_request_id=(
                "golden-path-activation-request"
            ),
            customer_id=CUSTOMER_ID,
        )
    )

    handoff = (
        main.customer_setup_handoff_service
        .issue(
            issuance_request_id=(
                "golden-path-handoff-request"
            ),
            setup_activation_id=(
                activation.setup_activation_id
            ),
            current_time=(
                datetime.now(
                    timezone.utc
                )
            ),
        )
    )

    handoff_credential = (
        handoff.handoff_credential
    )

    assert isinstance(
        handoff_credential,
        str,
    )

    assert handoff_credential

    # ========================================================
    # TEST-ONLY HTTP BRIDGE
    #
    # Production CustomerSetupHttpClient still performs its
    # normal httpx.post/get calls.
    #
    # The bridge routes those calls in-process to the actual
    # FastAPI routers produced by production composition.
    # ========================================================

    server_client = TestClient(
        app
    )

    http_calls: list[dict] = []

    def bridge_post(
        url,
        **kwargs,
    ):
        parsed = urlsplit(
            str(url)
        )

        request_path = (
            parsed.path
        )

        headers = dict(
            kwargs.get(
                "headers"
            )
            or {}
        )

        has_json = (
            "json"
            in kwargs
        )

        http_calls.append(
            {
                "method": "POST",
                "path": request_path,
                "authorization": (
                    _authorization_header(
                        headers
                    )
                ),
                "has_json": has_json,
                "json": (
                    kwargs.get(
                        "json"
                    )
                    if has_json
                    else None
                ),
            }
        )

        test_client_kwargs = {
            "headers": headers,
        }

        if has_json:
            test_client_kwargs[
                "json"
            ] = kwargs[
                "json"
            ]

        return server_client.post(
            request_path,
            **test_client_kwargs,
        )

    def bridge_get(
        url,
        **kwargs,
    ):
        parsed = urlsplit(
            str(url)
        )

        request_path = (
            parsed.path
        )

        headers = dict(
            kwargs.get(
                "headers"
            )
            or {}
        )

        http_calls.append(
            {
                "method": "GET",
                "path": request_path,
                "authorization": (
                    _authorization_header(
                        headers
                    )
                ),
                "has_json": False,
                "json": None,
            }
        )

        return server_client.get(
            request_path,
            headers=headers,
        )

    import backend.commercial.customer_setup_http_client as customer_setup_http_client_module

    monkeypatch.setattr(
        customer_setup_http_client_module.httpx,
        "post",
        bridge_post,
    )

    monkeypatch.setattr(
        customer_setup_http_client_module.httpx,
        "get",
        bridge_get,
    )

    # ========================================================
    # CUSTOMER-SIDE PRODUCTION OWNERS
    # ========================================================

    setup_http_client = (
        CustomerSetupHttpClient(
            setup_base_url=(
                SETUP_BASE_URL
            ),
            setup_handoff_credential=(
                handoff_credential
            ),
        )
    )

    installer = (
        CustomerMT5EX5InstallerService()
    )

    installation_calls = []

    def install(
        *,
        preflight_result,
        artifact_bytes,
        expected_sha256,
        expected_size_bytes,
    ):
        installation_calls.append(
            {
                "preflight_result": (
                    preflight_result
                ),
                "artifact_bytes": (
                    artifact_bytes
                ),
                "expected_sha256": (
                    expected_sha256
                ),
                "expected_size_bytes": (
                    expected_size_bytes
                ),
            }
        )

        assert (
            artifact_bytes
            == ARTIFACT_BYTES
        )

        assert (
            expected_sha256
            == ARTIFACT_SHA256
        )

        assert (
            expected_size_bytes
            == ARTIFACT_SIZE_BYTES
        )

        return (
            CustomerMT5EX5InstallationResult(
                terminal_path=(
                    preflight_result
                    .terminal_path
                ),
                data_path=(
                    preflight_result
                    .data_path
                ),
                account_fingerprint=(
                    preflight_result
                    .account_fingerprint
                ),
                installed_path=str(
                    tmp_path
                    / "installed"
                    / CUSTOMER_DEPLOYMENT_PACKAGE_ARTIFACT_NAME
                ),
                artifact_sha256=(
                    expected_sha256
                ),
                artifact_size_bytes=(
                    expected_size_bytes
                ),
                already_present=False,
            )
        )

    monkeypatch.setattr(
        installer,
        "install",
        install,
    )

    orchestration = (
        CustomerSetupOrchestrationService(
            setup_http_client=(
                setup_http_client
            ),
            ex5_installer_service=(
                installer
            ),
        )
    )

    preflight = _build_preflight(
        tmp_path
    )

    # ========================================================
    # ATTEMPT 1:
    # HANDOFF -> PROVISION -> BUILD_PENDING
    # ========================================================

    first = orchestration.run(
        preflight_result=preflight
    )

    assert (
        first.status
        == "build_pending"
    )

    assert (
        first.installation_result
        is None
    )

    continuation_credential = (
        orchestration
        ._continuation_credential
    )

    assert isinstance(
        continuation_credential,
        str,
    )

    assert continuation_credential.startswith(
        "tdbsc1."
    )

    assert (
        continuation_credential
        != handoff_credential
    )

    assert (
        orchestration
        ._continuation_account_fingerprint
        == ACCOUNT_FINGERPRINT
    )

    assert installation_calls == []

    build_requests = (
        main
        .customer_deployment_package_build_request_store
        .all()
    )

    assert len(
        build_requests
    ) == 1

    build_request = build_requests[
        0
    ]

    deployment_id = (
        build_request.deployment_id
    )

    assert isinstance(
        deployment_id,
        str,
    )

    assert deployment_id

    # Before external build completion, commercial
    # deployment activation has not occurred.
    assert (
        deployment_registry.get(
            deployment_id=(
                deployment_id
            )
        )
        is None
    )

    assert (
        entitlement_registry.is_active(
            deployment_id=(
                deployment_id
            )
        )
        is False
    )

    # ========================================================
    # EXTERNAL BUILD COMPLETION
    #
    # Simulate exactly the output owned by the asynchronous
    # package builder: one non-empty trusted-agent EX5 in the
    # authoritative publication directory.
    # ========================================================

    artifact_path = (
        publication.artifact_path(
            deployment_id=(
                deployment_id
            )
        )
    )

    artifact_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact_path.write_bytes(
        ARTIFACT_BYTES
    )

    published = (
        publication
        .get_published_package(
            deployment_id=(
                deployment_id
            )
        )
    )

    assert published is not None

    assert (
        published.artifact_path
        == artifact_path
    )

    assert (
        published.artifact_sha256
        == ARTIFACT_SHA256
    )

    assert (
        published.artifact_size_bytes
        == ARTIFACT_SIZE_BYTES
    )

    # ========================================================
    # ATTEMPT 2:
    # EXPLICIT RETRY -> CONTINUE -> READY -> PACKAGE -> INSTALL
    # ========================================================

    second = orchestration.run(
        preflight_result=preflight
    )

    assert (
        second.status
        == "installed"
    )

    assert (
        second.installation_result
        is not None
    )

    assert len(
        installation_calls
    ) == 1

    assert (
        installation_calls[
            0
        ][
            "artifact_bytes"
        ]
        == ARTIFACT_BYTES
    )

    # ========================================================
    # SERVER AUTHORITY CONVERGENCE
    # ========================================================

    deployment = (
        deployment_registry.get(
            deployment_id=(
                deployment_id
            )
        )
    )

    assert deployment is not None

    assert (
        deployment.customer_id
        == CUSTOMER_ID
    )

    assert (
        entitlement_registry.is_active(
            deployment_id=(
                deployment_id
            )
        )
        is True
    )

    bound_activation = (
        main
        .customer_setup_activation_service
        .get(
            setup_activation_id=(
                activation
                .setup_activation_id
            )
        )
    )

    assert bound_activation is not None

    assert (
        bound_activation.deployment_id
        == deployment_id
    )

    assert (
        bound_activation.status.value
        == "BOUND"
    )

    # ========================================================
    # CLIENT CONTINUATION STATE MUST CLEAR AFTER INSTALL
    # ========================================================

    assert (
        orchestration
        ._continuation_credential
        is None
    )

    assert (
        orchestration
        ._continuation_account_fingerprint
        is None
    )

    # ========================================================
    # TRANSPORT PROOF
    #
    # First call uses handoff authority.
    # Explicit retry uses only continuation authority.
    # Package download keeps continuation authority.
    # /continue has no client JSON body.
    # ========================================================

    assert [
        (
            call["method"],
            call["path"],
        )
        for call in http_calls
    ] == [
        (
            "POST",
            "/customer/setup/provision",
        ),
        (
            "POST",
            "/customer/setup/continue",
        ),
        (
            "GET",
            "/customer/setup/package",
        ),
    ]

    assert (
        http_calls[
            0
        ][
            "authorization"
        ]
        == (
            f"Bearer "
            f"{handoff_credential}"
        )
    )

    assert (
        http_calls[
            0
        ][
            "json"
        ]
        == {
            "account_fingerprint": (
                ACCOUNT_FINGERPRINT
            )
        }
    )

    assert (
        http_calls[
            1
        ][
            "authorization"
        ]
        == (
            f"Bearer "
            f"{continuation_credential}"
        )
    )

    assert (
        http_calls[
            1
        ][
            "has_json"
        ]
        is False
    )

    assert (
        http_calls[
            2
        ][
            "authorization"
        ]
        == (
            f"Bearer "
            f"{continuation_credential}"
        )
    )
