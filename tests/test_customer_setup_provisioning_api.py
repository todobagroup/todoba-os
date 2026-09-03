"""
Owner tests for asynchronous Customer Setup Provisioning API.
"""

import ast
from datetime import datetime
from datetime import timezone

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapPreparationResult,
    CustomerDeploymentBootstrapResult,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlement,
    CustomerDeploymentEntitlementStatus,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequest,
)
from backend.commercial.customer_deployment_package_publication import (
    CustomerDeploymentPublishedPackage,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeployment,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecrets,
)
from backend.commercial.customer_setup_build_continuation_service import (
    CustomerSetupBuildContinuationAuthorization,
    CustomerSetupBuildContinuationIssuanceResult,
    derive_customer_setup_build_continuation_issuance_request_id,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffAuthorization,
)
from backend.commercial.customer_setup_provisioning_api import (
    CustomerSetupProvisioningRequest,
    CustomerSetupProvisioningResponse,
    create_customer_setup_provisioning_router,
)


CUSTOMER_ID = "customer-001"
SETUP_ACTIVATION_ID = "setup-activation-001"
DEPLOYMENT_ID = "deployment-001"
AGENT_ID = "trusted-agent-001"
ACCOUNT_FINGERPRINT = "broker|login|server"
HANDOFF_ID = "a" * 32
ARTIFACT_SHA256 = "b" * 64
ARTIFACT_SIZE_BYTES = 1234

CONTINUATION_ID = "c" * 32

CONTINUATION_CREDENTIAL = (
    f"tdbsc1.{CONTINUATION_ID}."
    "continuation-secret-value"
)

CONTINUATION_ISSUED_AT = (
    "2026-09-01T04:41:53.000000Z"
)

CONTINUATION_EXPIRES_AT = (
    "2026-09-02T04:41:53.000000Z"
)

NOW = datetime(
    2026,
    9,
    1,
    4,
    41,
    53,
    tzinfo=timezone.utc,
)

CONTINUATION_ISSUANCE_REQUEST_ID = (
    derive_customer_setup_build_continuation_issuance_request_id(
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
        deployment_id=DEPLOYMENT_ID,
    )
)


def _status(
    value: str,
):
    return SimpleNamespace(
        value=value
    )


def _activation(
    *,
    status: str = "ACTIVE",
    customer_id: str = CUSTOMER_ID,
    deployment_id=None,
    setup_activation_id: str = SETUP_ACTIVATION_ID,
):
    return SimpleNamespace(
        setup_activation_id=(
            setup_activation_id
        ),
        customer_id=customer_id,
        status=_status(status),
        deployment_id=deployment_id,
    )


def _handoff(
    *,
    customer_id: str = CUSTOMER_ID,
    deployment_id=None,
):
    return CustomerSetupHandoffAuthorization(
        handoff_id=HANDOFF_ID,
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
        customer_id=customer_id,
        deployment_id=deployment_id,
    )


def _continuation_authorization(
    *,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str = DEPLOYMENT_ID,
):
    return CustomerSetupBuildContinuationAuthorization(
        continuation_id=CONTINUATION_ID,
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
        customer_id=customer_id,
        deployment_id=deployment_id,
    )


def _deployment(
    *,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str = DEPLOYMENT_ID,
    agent_id: str = AGENT_ID,
):
    return CustomerDeployment(
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
    )


def _secrets():
    return CustomerDeploymentSecrets(
        deployment_id=DEPLOYMENT_ID,
        agent_secret="agent-secret",
        execution_mission_signing_secret=(
            "execution-secret"
        ),
        control_mission_signing_secret=(
            "control-secret"
        ),
    )


def _prepared(
    *,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str = DEPLOYMENT_ID,
    account_fingerprint: str = ACCOUNT_FINGERPRINT,
    enrollment_request_id: str = SETUP_ACTIVATION_ID,
):
    deployment = _deployment(
        customer_id=customer_id,
        deployment_id=deployment_id,
    )

    secrets = _secrets()

    if deployment_id != DEPLOYMENT_ID:
        secrets = CustomerDeploymentSecrets(
            deployment_id=deployment_id,
            agent_secret="agent-secret",
            execution_mission_signing_secret=(
                "execution-secret"
            ),
            control_mission_signing_secret=(
                "control-secret"
            ),
        )

    return CustomerDeploymentBootstrapPreparationResult(
        enrollment_request_id=(
            enrollment_request_id
        ),
        deployment=deployment,
        secrets=secrets,
        account_fingerprint=(
            account_fingerprint
        ),
    )


def _activated(
    *,
    customer_id: str = CUSTOMER_ID,
    deployment_id: str = DEPLOYMENT_ID,
    agent_id: str = AGENT_ID,
    account_fingerprint: str = ACCOUNT_FINGERPRINT,
    enrollment_request_id: str = SETUP_ACTIVATION_ID,
):
    deployment = _deployment(
        customer_id=customer_id,
        deployment_id=deployment_id,
        agent_id=agent_id,
    )

    secrets = CustomerDeploymentSecrets(
        deployment_id=deployment_id,
        agent_secret="agent-secret",
        execution_mission_signing_secret=(
            "execution-secret"
        ),
        control_mission_signing_secret=(
            "control-secret"
        ),
    )

    return CustomerDeploymentBootstrapResult(
        enrollment_request_id=(
            enrollment_request_id
        ),
        deployment=deployment,
        secrets=secrets,
        account_fingerprint=(
            account_fingerprint
        ),
        projected_deployment_count=1,
    )


def _published(
    tmp_path: Path,
    *,
    deployment_id: str = DEPLOYMENT_ID,
):
    artifact = (
        tmp_path
        / "TODOBA_Trusted_Agent.ex5"
    )

    artifact.write_bytes(
        b"EX5"
    )

    return CustomerDeploymentPublishedPackage(
        deployment_id=deployment_id,
        artifact_path=artifact,
        artifact_sha256=ARTIFACT_SHA256,
        artifact_size_bytes=(
            ARTIFACT_SIZE_BYTES
        ),
    )


def _environment(
    tmp_path: Path,
    *,
    package_ready: bool = False,
    continuation_enabled: bool = False,
):
    authorizer = Mock(
        return_value=_handoff()
    )

    continuation_service = None

    if continuation_enabled:
        continuation_service = Mock()

        continuation_service.issue.return_value = (
            CustomerSetupBuildContinuationIssuanceResult(
                issuance_request_id=(
                    CONTINUATION_ISSUANCE_REQUEST_ID
                ),
                continuation_id=CONTINUATION_ID,
                setup_activation_id=(
                    SETUP_ACTIVATION_ID
                ),
                deployment_id=DEPLOYMENT_ID,
                issued_at=(
                    CONTINUATION_ISSUED_AT
                ),
                expires_at=(
                    CONTINUATION_EXPIRES_AT
                ),
                continuation_credential=(
                    CONTINUATION_CREDENTIAL
                ),
            )
        )

        continuation_service.authorize.return_value = (
            _continuation_authorization()
        )

    bootstrap_service = Mock()
    bootstrap_service.prepare_bootstrap.return_value = (
        _prepared()
    )
    bootstrap_service.recover_prepared_bootstrap.return_value = (
        _prepared()
    )
    bootstrap_service.activate_bootstrap.return_value = (
        _activated()
    )

    build_request_store = Mock()
    build_request_store.register.side_effect = (
        lambda request: request
    )

    package_publication = Mock()
    package_publication.get_published_package.return_value = (
        _published(tmp_path)
        if package_ready
        else None
    )

    entitlement_registry = Mock()
    entitlement_registry.activate.return_value = (
        CustomerDeploymentEntitlement(
            deployment_id=DEPLOYMENT_ID,
            status=(
                CustomerDeploymentEntitlementStatus
                .ACTIVE
            ),
        )
    )
    entitlement_registry.is_active.return_value = True

    setup_activation_service = Mock()
    setup_activation_service.get.return_value = (
        _activation()
    )
    setup_activation_service.bind.return_value = (
        _activation(
            status="BOUND",
            deployment_id=DEPLOYMENT_ID,
        )
    )

    return {
        "authorizer": authorizer,
        "continuation_service": (
            continuation_service
        ),
        "bootstrap_service": bootstrap_service,
        "build_request_store": (
            build_request_store
        ),
        "package_publication": (
            package_publication
        ),
        "entitlement_registry": (
            entitlement_registry
        ),
        "setup_activation_service": (
            setup_activation_service
        ),
    }


def _router(
    environment,
):
    return create_customer_setup_provisioning_router(
        authorize_setup_handoff=(
            environment[
                "authorizer"
            ]
        ),
        bootstrap_service=(
            environment[
                "bootstrap_service"
            ]
        ),
        build_request_store=(
            environment[
                "build_request_store"
            ]
        ),
        package_publication=(
            environment[
                "package_publication"
            ]
        ),
        entitlement_registry=(
            environment[
                "entitlement_registry"
            ]
        ),
        setup_activation_service=(
            environment[
                "setup_activation_service"
            ]
        ),
        continuation_service=(
            environment[
                "continuation_service"
            ]
        ),
        clock=lambda: NOW,
    )


def _client(
    environment,
):
    app = FastAPI()

    app.include_router(
        _router(environment)
    )

    return TestClient(
        app,
        raise_server_exceptions=False,
    )


def _post(
    client,
    *,
    authorization=(
        "Bearer tdbsh1.test.secret"
    ),
    account_fingerprint=(
        ACCOUNT_FINGERPRINT
    ),
    extra=None,
):
    headers = {}

    if authorization is not None:
        headers["Authorization"] = (
            authorization
        )

    payload = {
        "account_fingerprint": (
            account_fingerprint
        )
    }

    if extra is not None:
        payload.update(extra)

    return client.post(
        "/customer/setup/provision",
        headers=headers,
        json=payload,
    )


def _post_continue(
    client,
    *,
    authorization=(
        "Bearer "
        + CONTINUATION_CREDENTIAL
    ),
    account_fingerprint=(
        ACCOUNT_FINGERPRINT
    ),
):
    return client.post(
        "/customer/setup/continue",
        headers={
            "Authorization": authorization,
        },
    )


def test_package_missing_returns_build_pending_202(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=False,
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 202
    assert response.json() == {
        "status": "build_pending"
    }

    environment[
        "bootstrap_service"
    ].activate_bootstrap.assert_not_called()

    environment[
        "entitlement_registry"
    ].activate.assert_not_called()

    environment[
        "setup_activation_service"
    ].bind.assert_not_called()


def test_pending_registers_exact_immutable_build_request(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    _post(
        _client(environment)
    )

    registered = (
        environment[
            "build_request_store"
        ].register.call_args.args[0]
    )

    assert isinstance(
        registered,
        CustomerDeploymentPackageBuildRequest,
    )

    assert registered.deployment_id == DEPLOYMENT_ID
    assert (
        registered.bootstrap_request_id
        == SETUP_ACTIVATION_ID
    )


def test_ready_publication_finishes_activation_entitlement_and_bind(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ready",
        "artifact_sha256": ARTIFACT_SHA256,
        "artifact_size_bytes": (
            ARTIFACT_SIZE_BYTES
        ),
    }

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.assert_called_once_with(
        enrollment_request_id=(
            SETUP_ACTIVATION_ID
        ),
        customer_id=CUSTOMER_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )

    environment[
        "bootstrap_service"
    ].activate_bootstrap.assert_called_once_with(
        enrollment_request_id=(
            SETUP_ACTIVATION_ID
        ),
        customer_id=CUSTOMER_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )

    environment[
        "entitlement_registry"
    ].activate.assert_called_once_with(
        deployment_id=DEPLOYMENT_ID
    )

    environment[
        "setup_activation_service"
    ].bind.assert_called_once_with(
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
        deployment_id=DEPLOYMENT_ID,
    )


def test_account_fingerprint_is_normalized(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    response = _post(
        _client(environment),
        account_fingerprint=(
            f"  {ACCOUNT_FINGERPRINT}  "
        ),
    )

    assert response.status_code == 202

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.assert_called_once_with(
        enrollment_request_id=(
            SETUP_ACTIVATION_ID
        ),
        customer_id=CUSTOMER_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Basic abc",
        "Bearer",
        "Bearer ",
        "Bearer    ",
        "bearer token",
        "Bearer token ",
        "Bearer  token",
    ],
)
def test_missing_or_invalid_setup_bearer_fails_closed(
    tmp_path: Path,
    authorization,
):
    environment = _environment(
        tmp_path
    )

    response = _post(
        _client(environment),
        authorization=authorization,
    )

    assert response.status_code == 401

    assert (
        response.headers[
            "www-authenticate"
        ]
        == "Bearer"
    )

    environment[
        "authorizer"
    ].assert_not_called()


def test_r3_value_error_is_unauthorized(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "authorizer"
    ].side_effect = ValueError(
        "invalid handoff"
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 401


def test_unknown_handoff_is_unauthorized(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "authorizer"
    ].return_value = None

    response = _post(
        _client(environment)
    )

    assert response.status_code == 401


def test_r3_runtime_fault_remains_server_fault(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "authorizer"
    ].side_effect = RuntimeError(
        "handoff store failure"
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 500


def test_invalid_handoff_projection_fails_closed(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "authorizer"
    ].return_value = SimpleNamespace(
        customer_id=CUSTOMER_ID,
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 500


@pytest.mark.parametrize(
    "field,value",
    [
        ("customer_id", "forged"),
        ("setup_activation_id", "forged"),
        ("deployment_id", "forged"),
        ("agent_id", "forged"),
        ("credential_id", "forged"),
        ("access_credential", "secret"),
        ("payment_id", "forged"),
        ("subscription_id", "forged"),
        ("mt5_password", "secret"),
        ("login", 123456),
        ("server", "broker-server"),
        ("margin_mode", "HEDGING"),
    ],
)
def test_request_rejects_customer_controlled_identity_and_secrets(
    tmp_path: Path,
    field,
    value,
):
    environment = _environment(
        tmp_path
    )

    response = _post(
        _client(environment),
        extra={
            field: value
        },
    )

    assert response.status_code == 422

    environment[
        "authorizer"
    ].assert_not_called()


@pytest.mark.parametrize(
    "account_fingerprint",
    [
        "",
        " ",
        "   ",
    ],
)
def test_empty_account_fingerprint_is_rejected(
    tmp_path: Path,
    account_fingerprint,
):
    environment = _environment(
        tmp_path
    )

    response = _post(
        _client(environment),
        account_fingerprint=(
            account_fingerprint
        ),
    )

    assert response.status_code == 422


def test_authorized_activation_must_exist(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "setup_activation_service"
    ].get.return_value = None

    response = _post(
        _client(environment)
    )

    assert response.status_code == 500


def test_activation_identity_must_match_handoff(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        setup_activation_id=(
            "different-activation"
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_activation_customer_must_match_handoff(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        customer_id="different-customer"
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_suspended_activation_fails_403(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        status="SUSPENDED"
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 403

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.assert_not_called()


def test_unknown_activation_status_fails_closed(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        status="UNKNOWN"
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_active_handoff_must_not_claim_deployment(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "authorizer"
    ].return_value = _handoff(
        deployment_id=DEPLOYMENT_ID
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.assert_not_called()


def test_prepared_request_identity_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.return_value = (
        _prepared(
            enrollment_request_id=(
                "different-request"
            )
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_prepared_customer_identity_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.return_value = (
        _prepared(
            customer_id=(
                "different-customer"
            )
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_prepared_account_identity_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.return_value = (
        _prepared(
            account_fingerprint=(
                "different-account"
            )
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_invalid_preparation_result_fails_closed(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.return_value = (
        SimpleNamespace()
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_build_request_store_result_must_converge(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path
    )

    environment[
        "build_request_store"
    ].register.return_value = (
        CustomerDeploymentPackageBuildRequest(
            deployment_id=DEPLOYMENT_ID,
            bootstrap_request_id=(
                "different-bootstrap"
            ),
        )
    )
    environment[
        "build_request_store"
    ].register.side_effect = None

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_publication_deployment_identity_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "package_publication"
    ].get_published_package.return_value = (
        _published(
            tmp_path,
            deployment_id=(
                "different-deployment"
            ),
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )

    environment[
        "bootstrap_service"
    ].activate_bootstrap.assert_not_called()


def test_activated_request_identity_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "bootstrap_service"
    ].activate_bootstrap.return_value = (
        _activated(
            enrollment_request_id=(
                "different-request"
            )
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_activated_deployment_identity_must_match_prepared(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "bootstrap_service"
    ].activate_bootstrap.return_value = (
        _activated(
            deployment_id=(
                "different-deployment"
            )
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_activated_customer_identity_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "bootstrap_service"
    ].activate_bootstrap.return_value = (
        _activated(
            customer_id=(
                "different-customer"
            )
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_activated_account_identity_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "bootstrap_service"
    ].activate_bootstrap.return_value = (
        _activated(
            account_fingerprint=(
                "different-account"
            )
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_entitlement_result_must_match_deployment(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "entitlement_registry"
    ].activate.return_value = (
        CustomerDeploymentEntitlement(
            deployment_id=(
                "different-deployment"
            ),
            status=(
                CustomerDeploymentEntitlementStatus
                .ACTIVE
            ),
        )
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_bind_identity_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "setup_activation_service"
    ].bind.return_value = _activation(
        setup_activation_id=(
            "different-activation"
        ),
        status="BOUND",
        deployment_id=DEPLOYMENT_ID,
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_bind_customer_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "setup_activation_service"
    ].bind.return_value = _activation(
        customer_id="different-customer",
        status="BOUND",
        deployment_id=DEPLOYMENT_ID,
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_bind_deployment_must_match(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "setup_activation_service"
    ].bind.return_value = _activation(
        status="BOUND",
        deployment_id=(
            "different-deployment"
        ),
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_bind_must_finish_bound(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "setup_activation_service"
    ].bind.return_value = _activation(
        status="ACTIVE",
        deployment_id=DEPLOYMENT_ID,
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_bound_retry_reads_only_and_returns_ready(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "authorizer"
    ].return_value = _handoff(
        deployment_id=DEPLOYMENT_ID
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        status="BOUND",
        deployment_id=DEPLOYMENT_ID,
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"

    environment[
        "entitlement_registry"
    ].is_active.assert_called_once_with(
        deployment_id=DEPLOYMENT_ID
    )

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.assert_not_called()

    environment[
        "bootstrap_service"
    ].activate_bootstrap.assert_not_called()

    environment[
        "build_request_store"
    ].register.assert_not_called()

    environment[
        "entitlement_registry"
    ].activate.assert_not_called()

    environment[
        "setup_activation_service"
    ].bind.assert_not_called()


def test_bound_retry_never_reactivates_suspended_entitlement(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "authorizer"
    ].return_value = _handoff(
        deployment_id=DEPLOYMENT_ID
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        status="BOUND",
        deployment_id=DEPLOYMENT_ID,
    )

    environment[
        "entitlement_registry"
    ].is_active.return_value = False

    response = _post(
        _client(environment)
    )

    assert response.status_code == 403

    environment[
        "entitlement_registry"
    ].activate.assert_not_called()


def test_bound_retry_handoff_deployment_must_match_r2(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "authorizer"
    ].return_value = _handoff(
        deployment_id=(
            "different-deployment"
        )
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        status="BOUND",
        deployment_id=DEPLOYMENT_ID,
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_bound_retry_requires_published_package(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=False,
    )

    environment[
        "authorizer"
    ].return_value = _handoff(
        deployment_id=DEPLOYMENT_ID
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        status="BOUND",
        deployment_id=DEPLOYMENT_ID,
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_bound_retry_requires_deployment_identity(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    environment[
        "authorizer"
    ].return_value = _handoff(
        deployment_id=DEPLOYMENT_ID
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        status="BOUND",
        deployment_id=None,
    )

    assert (
        _post(
            _client(environment)
        ).status_code
        == 500
    )


def test_pending_response_model_rejects_artifact_metadata():
    with pytest.raises(
        ValueError
    ):
        CustomerSetupProvisioningResponse(
            status="build_pending",
            artifact_sha256=ARTIFACT_SHA256,
        )


def test_ready_response_model_requires_metadata():
    with pytest.raises(
        ValueError
    ):
        CustomerSetupProvisioningResponse(
            status="ready"
        )


def test_http_response_exposes_only_safe_metadata(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
    )

    response = _post(
        _client(environment)
    )

    serialized = response.json()

    assert set(serialized) == {
        "status",
        "artifact_sha256",
        "artifact_size_bytes",
    }

    for forbidden in (
        "customer_id",
        "setup_activation_id",
        "deployment_id",
        "agent_id",
        "credential_id",
        "access_credential",
        "package_path",
        "account_fingerprint",
    ):
        assert forbidden not in serialized


def test_continuation_route_is_absent_without_owner(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
    )

    response = _post_continue(
        _client(environment)
    )

    assert response.status_code == 404


def test_pending_with_continuation_owner_issues_one_continuation(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=False,
        continuation_enabled=True,
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 202

    assert response.json() == {
        "status": "build_pending",
        "continuation_credential": (
            CONTINUATION_CREDENTIAL
        ),
        "continuation_expires_at": (
            CONTINUATION_EXPIRES_AT
        ),
    }

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )

    assert (
        response.headers[
            "pragma"
        ]
        == "no-cache"
    )

    environment[
        "continuation_service"
    ].issue.assert_called_once_with(
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
        deployment_id=DEPLOYMENT_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
        current_time=NOW,
    )


def test_ready_initial_request_does_not_issue_continuation(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
        continuation_enabled=True,
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"

    environment[
        "continuation_service"
    ].issue.assert_not_called()


def test_pending_response_rejects_partial_continuation_authority():
    with pytest.raises(
        ValueError,
        match="must appear together",
    ):
        CustomerSetupProvisioningResponse(
            status="build_pending",
            continuation_credential=(
                CONTINUATION_CREDENTIAL
            ),
        )


def test_ready_response_rejects_continuation_authority():
    with pytest.raises(
        ValueError,
        match="must not contain continuation",
    ):
        CustomerSetupProvisioningResponse(
            status="ready",
            artifact_sha256=ARTIFACT_SHA256,
            artifact_size_bytes=(
                ARTIFACT_SIZE_BYTES
            ),
            continuation_credential=(
                CONTINUATION_CREDENTIAL
            ),
            continuation_expires_at=(
                CONTINUATION_EXPIRES_AT
            ),
        )


def test_provisioning_response_repr_redacts_continuation_secret():
    result = CustomerSetupProvisioningResponse(
        status="build_pending",
        continuation_credential=(
            CONTINUATION_CREDENTIAL
        ),
        continuation_expires_at=(
            CONTINUATION_EXPIRES_AT
        ),
    )

    assert (
        CONTINUATION_CREDENTIAL
        not in repr(result)
    )


def test_continue_pending_recovers_existing_build_without_register(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=False,
        continuation_enabled=True,
    )

    response = _post_continue(
        _client(environment)
    )

    assert response.status_code == 202

    assert response.json() == {
        "status": "build_pending"
    }

    authorize = environment[
        "continuation_service"
    ].authorize

    assert authorize.call_count == 2

    assert (
        authorize.call_args_list[0].kwargs
        == {
            "continuation_credential": (
                CONTINUATION_CREDENTIAL
            ),
            "current_time": NOW,
        }
    )

    assert (
        authorize.call_args_list[1].kwargs
        == {
            "continuation_credential": (
                CONTINUATION_CREDENTIAL
            ),
            "current_time": NOW,
            "account_fingerprint": (
                ACCOUNT_FINGERPRINT
            ),
        }
    )

    environment[
        "authorizer"
    ].assert_not_called()

    environment[
        "bootstrap_service"
    ].recover_prepared_bootstrap.assert_called_once_with(
        enrollment_request_id=(
            SETUP_ACTIVATION_ID
        )
    )

    environment[
        "build_request_store"
    ].register.assert_not_called()

    environment[
        "bootstrap_service"
    ].prepare_bootstrap.assert_not_called()

    environment[
        "bootstrap_service"
    ].activate_bootstrap.assert_not_called()

    environment[
        "entitlement_registry"
    ].activate.assert_not_called()

    environment[
        "setup_activation_service"
    ].bind.assert_not_called()


def test_continue_ready_completes_exact_recovered_build(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
        continuation_enabled=True,
    )

    response = _post_continue(
        _client(environment)
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ready",
        "artifact_sha256": ARTIFACT_SHA256,
        "artifact_size_bytes": (
            ARTIFACT_SIZE_BYTES
        ),
    }

    environment[
        "authorizer"
    ].assert_not_called()

    environment[
        "build_request_store"
    ].register.assert_not_called()

    environment[
        "bootstrap_service"
    ].recover_prepared_bootstrap.assert_called_once_with(
        enrollment_request_id=(
            SETUP_ACTIVATION_ID
        )
    )

    environment[
        "bootstrap_service"
    ].activate_bootstrap.assert_called_once_with(
        enrollment_request_id=(
            SETUP_ACTIVATION_ID
        ),
        customer_id=CUSTOMER_ID,
        account_fingerprint=(
            ACCOUNT_FINGERPRINT
        ),
    )

    environment[
        "entitlement_registry"
    ].activate.assert_called_once_with(
        deployment_id=DEPLOYMENT_ID
    )

    environment[
        "setup_activation_service"
    ].bind.assert_called_once_with(
        setup_activation_id=(
            SETUP_ACTIVATION_ID
        ),
        deployment_id=DEPLOYMENT_ID,
    )


def test_invalid_continuation_fails_before_recovery(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        continuation_enabled=True,
    )

    environment[
        "continuation_service"
    ].authorize.side_effect = ValueError(
        "invalid continuation"
    )

    response = _post_continue(
        _client(environment),
        authorization=(
            "Bearer invalid-continuation"
        ),
    )

    assert response.status_code == 401

    environment[
        "authorizer"
    ].assert_not_called()

    environment[
        "bootstrap_service"
    ].recover_prepared_bootstrap.assert_not_called()

    environment[
        "build_request_store"
    ].register.assert_not_called()


def test_continue_authorization_result_type_is_strict(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        continuation_enabled=True,
    )

    environment[
        "continuation_service"
    ].authorize.return_value = object()

    response = _post_continue(
        _client(environment)
    )

    assert response.status_code == 500

    environment[
        "bootstrap_service"
    ].recover_prepared_bootstrap.assert_not_called()


def test_continue_recovered_deployment_must_match_authority(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
        continuation_enabled=True,
    )

    environment[
        "bootstrap_service"
    ].recover_prepared_bootstrap.return_value = (
        _prepared(
            deployment_id=(
                "different-deployment"
            )
        )
    )

    response = _post_continue(
        _client(environment)
    )

    assert response.status_code == 500

    environment[
        "build_request_store"
    ].register.assert_not_called()

    environment[
        "bootstrap_service"
    ].activate_bootstrap.assert_not_called()


def test_continue_bound_retry_remains_read_only(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        package_ready=True,
        continuation_enabled=True,
    )

    environment[
        "setup_activation_service"
    ].get.return_value = _activation(
        status="BOUND",
        deployment_id=DEPLOYMENT_ID,
    )

    response = _post_continue(
        _client(environment)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"

    environment[
        "bootstrap_service"
    ].recover_prepared_bootstrap.assert_not_called()

    environment[
        "build_request_store"
    ].register.assert_not_called()

    environment[
        "bootstrap_service"
    ].activate_bootstrap.assert_not_called()

    environment[
        "entitlement_registry"
    ].activate.assert_not_called()

    environment[
        "setup_activation_service"
    ].bind.assert_not_called()


def test_bad_continuation_issuance_type_fails_closed(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        continuation_enabled=True,
    )

    environment[
        "continuation_service"
    ].issue.return_value = object()

    response = _post(
        _client(environment)
    )

    assert response.status_code == 500


def test_continuation_issuance_identity_must_converge(
    tmp_path: Path,
):
    environment = _environment(
        tmp_path,
        continuation_enabled=True,
    )

    environment[
        "continuation_service"
    ].issue.return_value = (
        CustomerSetupBuildContinuationIssuanceResult(
            issuance_request_id=(
                CONTINUATION_ISSUANCE_REQUEST_ID
            ),
            continuation_id=CONTINUATION_ID,
            setup_activation_id=(
                SETUP_ACTIVATION_ID
            ),
            deployment_id=(
                "different-deployment"
            ),
            issued_at=CONTINUATION_ISSUED_AT,
            expires_at=(
                CONTINUATION_EXPIRES_AT
            ),
            continuation_credential=(
                CONTINUATION_CREDENTIAL
            ),
        )
    )

    response = _post(
        _client(environment)
    )

    assert response.status_code == 500


def test_source_has_no_sync_onboarding_or_build_ownership():
    source = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "backend"
        / "commercial"
        / "customer_setup_provisioning_api.py"
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)
    module_docstring = ast.get_docstring(
        tree,
        clean=False,
    )

    audited_source = source

    if module_docstring is not None:
        audited_source = source.replace(
            module_docstring,
            "",
            1,
        )

    for forbidden in (
        "CustomerOnboardingService",
        "CustomerAccessProvisioningService",
        "CustomerAccessCredentialRegistry",
        ".onboard(",
        "build_package(",
        "MetaEditor",
        "initialize_empty",
        "backend.main",
    ):
        assert forbidden not in audited_source
