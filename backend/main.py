from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.brain.memory import memory_engine
from backend.brain.models.experience import Experience
from backend.brain_engine import brain_engine


from backend.config import (
    TODOBA_CONTROL_PLANE_DATA_ROOT,
    TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY,
    TODOBA_EXECUTOR_ID,
    TODOBA_EXECUTOR_SECRET,
    TODOBA_RUNTIME_MODE,
    get_customer_package_root,
)
from backend.commercial.customer_access_credential_registry import (
    CustomerAccessCredentialRegistry,
)
from backend.commercial.customer_authentication_dependency import (
    create_customer_authentication_dependency,
)
from backend.commercial.customer_authenticator import (
    CustomerAuthenticator,
)
from backend.commercial.customer_deployment_authorizer import (
    CustomerDeploymentAuthorizer,
)
from backend.commercial.customer_deployment_bootstrap_service import (
    CustomerDeploymentBootstrapService,
    CustomerDeploymentBootstrapStore,
)
from backend.commercial.customer_deployment_enrollment_service import (
    CustomerDeploymentEnrollmentService,
)
from backend.commercial.customer_deployment_package_build_request_store import (
    CustomerDeploymentPackageBuildRequestStore,
)
from backend.commercial.customer_setup_activation_service import (
    CustomerSetupActivationService,
    CustomerSetupActivationStore,
)
from backend.commercial.customer_setup_handoff_authorizer import (
    CustomerSetupHandoffAuthorizer,
)
from backend.commercial.customer_setup_handoff_service import (
    CustomerSetupHandoffService,
    CustomerSetupHandoffStore,
)
from backend.commercial.customer_setup_package_api import (
    create_customer_setup_package_router,
)
from backend.commercial.customer_setup_provisioning_api import (
    create_customer_setup_provisioning_router,
)
from backend.commercial.customer_deployment_entitlement_authorizer import (
    CustomerDeploymentEntitlementAuthorizer,
)
from backend.commercial.customer_deployment_entitlement_registry import (
    CustomerDeploymentEntitlementRegistry,
)
from backend.commercial.customer_deployment_master_key import (
    decode_customer_deployment_master_key,
)
from backend.commercial.customer_deployment_package_api import (
    create_customer_deployment_package_router,
)
from backend.commercial.customer_deployment_package_publication import (
    CustomerDeploymentPackagePublication,
)
from backend.commercial.customer_deployment_registry import (
    CustomerDeploymentRegistry,
)
from backend.commercial.customer_identity_registry import (
    CustomerIdentityRegistry,
)
from backend.commercial.customer_deployment_runtime_projection import (
    CustomerDeploymentRuntimeProjection,
)
from backend.commercial.customer_deployment_secret_store import (
    CustomerDeploymentSecretStore,
)
from backend.runtime.runtime_mode import (
    RuntimeMode,
    create_runtime,
)
from backend.runtime.todoba_runtime import (
    TODOBARuntime,
)

from backend.trading.control.control_mission_api import (
    create_control_mission_router,
)
from backend.trading.control.control_mission_delivery_bridge import (
    ControlMissionDeliveryBridge,
)
from backend.trading.control.control_mission_delivery_expiration_policy import (
    ControlMissionDeliveryExpirationPolicy,
)
from backend.trading.control.control_mission_delivery_lease_persistence import (
    ControlMissionDeliveryLeasePersistence,
)
from backend.trading.control.control_mission_delivery_lease_recovery import (
    ControlMissionDeliveryLeaseRecovery,
)
from backend.trading.control.control_mission_delivery_lease_registry import (
    ControlMissionDeliveryLeaseRegistry,
)
from backend.trading.control.control_mission_delivery_lease_service import (
    ControlMissionDeliveryLeaseService,
)
from backend.trading.control.control_mission_delivery_redelivery_processor import (
    ControlMissionDeliveryRedeliveryProcessor,
)
from backend.trading.control.control_mission_injection_api import (
    create_control_mission_injection_router,
)
from backend.trading.control.control_mission_lifecycle_api import (
    create_control_mission_lifecycle_router,
)
from backend.trading.control.control_mission_lifecycle_scheduler import (
    ControlMissionLifecycleScheduler,
)
from backend.trading.control.control_mission_lifecycle_service import (
    ControlMissionLifecycleService,
)
from backend.trading.control.control_mission_persistence import (
    ControlMissionPersistence,
)
from backend.trading.control.control_mission_record_persistence import (
    ControlMissionRecordPersistence,
)
from backend.trading.control.control_mission_record_recovery import (
    ControlMissionRecordRecovery,
)
from backend.trading.control.control_mission_recovery import (
    ControlMissionRecovery,
)
from backend.trading.control.control_mission_registry import (
    ControlMissionRegistry,
)
from backend.trading.control.control_mission_repository import (
    ControlMissionRepository,
)
from backend.trading.control.control_mission_service import (
    ControlMissionService,
)
from backend.trading.control.control_mission_signer import (
    ControlMissionSigner,
)
from backend.trading.control.control_mission_signer_v2 import (
    ControlMissionSignerV2,
)
from backend.trading.control.control_mission_store import (
    ControlMissionStore,
)
from backend.trading.execution.broker_execution_evidence_api import (
    create_broker_execution_evidence_router,
)
from backend.trading.execution.broker_execution_evidence_processor import (
    BrokerExecutionEvidenceProcessor,
)
from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission_acknowledgement_api import (
    create_execution_mission_acknowledgement_router,
)
from backend.trading.execution.execution_mission_acknowledgement_processor import (
    ExecutionMissionAcknowledgementProcessor,
)
from backend.trading.execution.execution_mission_acknowledgement_store import (
    ExecutionMissionAcknowledgementStore,
)
from backend.trading.execution.execution_mission_api import (
    create_execution_mission_router,
)
from backend.trading.execution.execution_mission_completed_api import (
    create_execution_mission_completed_router,
)
from backend.trading.execution.execution_mission_completed_processor import (
    ExecutionMissionCompletedProcessor,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_delivery_lease_persistence import (
    ExecutionMissionDeliveryLeasePersistence,
)
from backend.trading.execution.execution_mission_delivery_lease_recovery import (
    ExecutionMissionDeliveryLeaseRecovery,
)
from backend.trading.execution.execution_mission_delivery_lease_registry import (
    ExecutionMissionDeliveryLeaseRegistry,
)
from backend.trading.execution.execution_mission_delivery_lease_service import (
    ExecutionMissionDeliveryLeaseService,
)
from backend.trading.execution.execution_mission_signer import (
    ExecutionMissionSigner,
)
from backend.trading.execution.execution_mission_signer_v2 import (
    ExecutionMissionSignerV2,
)
from backend.trading.execution.execution_mission_delivery_redelivery_processor import (
    ExecutionMissionDeliveryRedeliveryProcessor,
)
from backend.trading.execution.execution_mission_evidence_idempotency_registry import (
    ExecutionMissionEvidenceIdempotencyRegistry,
)
from backend.trading.execution.execution_mission_evidence_intake import (
    ExecutionMissionEvidenceIntake,
)
from backend.trading.execution.execution_mission_evidence_persistence import (
    ExecutionMissionEvidencePersistence,
)
from backend.trading.execution.execution_mission_execution_started_api import (
    create_execution_mission_execution_started_router,
)
from backend.trading.execution.execution_mission_execution_started_processor import (
    ExecutionMissionExecutionStartedProcessor,
)
from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)
from backend.trading.execution.execution_mission_failed_api import (
    create_execution_mission_failed_router,
)
from backend.trading.execution.execution_mission_failed_processor import (
    ExecutionMissionFailedProcessor,
)
from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
)
from backend.trading.execution.execution_mission_injection_api import (
    create_execution_mission_injection_router,
)
from backend.trading.execution.execution_mission_delivery_expiration_policy import (
    ExecutionMissionDeliveryExpirationPolicy,
)
from backend.trading.execution.execution_mission_lifecycle_scheduler import (
    ExecutionMissionLifecycleScheduler,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_record_cleanup import (
    ExecutionMissionRecordCleanup,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_record_recovery import (
    ExecutionMissionRecordRecovery,
)
from backend.trading.execution.execution_mission_record_retention_policy import (
    ExecutionMissionRecordRetentionPolicy,
)
from backend.trading.execution.execution_mission_record_retention_scheduler import (
    ExecutionMissionRecordRetentionScheduler,
)
from backend.trading.execution.execution_mission_release_guard import (
    ExecutionMissionReleaseGuard,
)
from backend.trading.execution.execution_mission_recovery import (
    ExecutionMissionRecovery,
)
from backend.trading.execution.execution_mission_registry import (
    ExecutionMissionRegistry,
)
from backend.trading.execution.execution_mission_repository import (
    ExecutionMissionRepository,
)
from backend.trading.execution.execution_mission_service import (
    ExecutionMissionService,
)
from backend.trading.execution.execution_mission_status_api import (
    create_execution_mission_status_router,
)
from backend.trading.execution.execution_mission_store import (
    ExecutionMissionStore,
)
from backend.trading.execution.broker_state_api import (
    create_broker_state_router,
)
from backend.trading.execution.broker_state_store import (
    BrokerStateStore,
)
from backend.trading.execution.execution_target_registry import (
    ExecutionTargetRegistry,
)
from backend.trading.execution.executor_authenticator import (
    ExecutorAuthenticator,
)
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
)
from backend.trading.execution.trusted_agent_credential_registry import (
    TrustedAgentCredentialRegistry,
)
from backend.trading.execution.trusted_agent_signing_key_registry import (
    TrustedAgentSigningKeyRegistry,
)
from backend.trading.execution.trusted_agent_account_binding_guard import (
    TrustedAgentAccountBindingGuard,
)
from backend.trading.execution.trusted_agent_account_binding_store import (
    TrustedAgentAccountBindingStore,
)
from backend.trading.execution.persistent_security_sequence_allocator import (
    PersistentSecuritySequenceAllocator,
)
from backend.trading.execution.persistent_security_sequence_binding_store import (
    PersistentSecuritySequenceBindingStore,
)
from backend.trading.execution.security_sequence_assignment_service import (
    SecuritySequenceAssignmentService,
)


MISSION_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "execution_missions.json"
)

MISSION_RECORD_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "execution_mission_records.json"
)

MISSION_EVIDENCE_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "execution_mission_evidence.json"
)

MISSION_DELIVERY_LEASE_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "execution_mission_delivery_leases.json"
)

CONTROL_MISSION_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "control_missions.json"
)

CONTROL_MISSION_RECORD_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "control_mission_records.json"
)

CONTROL_MISSION_DELIVERY_LEASE_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "control_mission_delivery_leases.json"
)

EXECUTION_SECURITY_SEQUENCE_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "execution_security_sequence.json"
)

EXECUTION_SECURITY_SEQUENCE_BINDING_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "execution_security_sequence_bindings.json"
)

CONTROL_SECURITY_SEQUENCE_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "control_security_sequence.json"
)

CONTROL_SECURITY_SEQUENCE_BINDING_STORAGE_PATH = (
    Path("data")
    / "trading"
    / "control_security_sequence_bindings.json"
)

CUSTOMER_DEPLOYMENT_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_deployments.json"
)

CUSTOMER_DEPLOYMENT_SECRET_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_deployment_secrets.json"
)

CUSTOMER_IDENTITY_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_identities.json"
)

CUSTOMER_ACCESS_CREDENTIAL_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_access_credentials.json"
)

CUSTOMER_DEPLOYMENT_ENTITLEMENT_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_deployment_entitlements.json"
)

CUSTOMER_SETUP_ACTIVATION_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_setup_activations.json"
)

CUSTOMER_SETUP_HANDOFF_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_setup_handoffs.json"
)

CUSTOMER_DEPLOYMENT_BOOTSTRAP_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_deployment_bootstraps.json"
)

CUSTOMER_DEPLOYMENT_PACKAGE_BUILD_REQUEST_STORAGE_ROOT = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "commercial"
    / "customer_deployment_package_build_requests"
)

TRUSTED_AGENT_ACCOUNT_BINDING_STORAGE_PATH = (
    TODOBA_CONTROL_PLANE_DATA_ROOT
    / "trading"
    / "trusted_agent_account_bindings.json"
)


customer_deployment_registry = (
    CustomerDeploymentRegistry(
        CUSTOMER_DEPLOYMENT_STORAGE_PATH
    )
)

customer_deployment_secret_store = (
    CustomerDeploymentSecretStore(
        CUSTOMER_DEPLOYMENT_SECRET_STORAGE_PATH,
        master_key=(
            decode_customer_deployment_master_key(
                TODOBA_CUSTOMER_DEPLOYMENT_MASTER_KEY
            )
        ),
    )
)

customer_identity_registry = (
    CustomerIdentityRegistry(
        CUSTOMER_IDENTITY_STORAGE_PATH
    )
)

customer_access_credential_registry = (
    CustomerAccessCredentialRegistry(
        CUSTOMER_ACCESS_CREDENTIAL_STORAGE_PATH,
        customer_identity_registry=(
            customer_identity_registry
        ),
    )
)

customer_authenticator = (
    CustomerAuthenticator(
        credential_registry=(
            customer_access_credential_registry
        )
    )
)

customer_authentication_dependency = (
    create_customer_authentication_dependency(
        customer_authenticator
    )
)

customer_deployment_authorizer = (
    CustomerDeploymentAuthorizer(
        deployment_registry=(
            customer_deployment_registry
        )
    )
)

customer_deployment_entitlement_registry = (
    CustomerDeploymentEntitlementRegistry(
        CUSTOMER_DEPLOYMENT_ENTITLEMENT_STORAGE_PATH,
        deployment_registry=(
            customer_deployment_registry
        ),
    )
)

customer_deployment_entitlement_authorizer = (
    CustomerDeploymentEntitlementAuthorizer(
        entitlement_registry=(
            customer_deployment_entitlement_registry
        )
    )
)

customer_deployment_package_publication = (
    CustomerDeploymentPackagePublication(
        package_root=(
            get_customer_package_root()
        )
    )
)

trusted_agent_account_binding_store = (
    TrustedAgentAccountBindingStore(
        TRUSTED_AGENT_ACCOUNT_BINDING_STORAGE_PATH
    )
)

trusted_agent_account_binding_guard = (
    TrustedAgentAccountBindingGuard(
        trusted_agent_account_binding_store
    )
)

trusted_agent_credential_registry = (
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

customer_deployment_runtime_projection = (
    CustomerDeploymentRuntimeProjection(
        deployment_registry=(
            customer_deployment_registry
        ),
        secret_store=(
            customer_deployment_secret_store
        ),
        account_binding_store=(
            trusted_agent_account_binding_store
        ),
        credential_registry=(
            trusted_agent_credential_registry
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


_customer_setup_runtime_composed = False

customer_setup_activation_store = None
customer_setup_handoff_store = None
customer_deployment_bootstrap_store = None
customer_deployment_package_build_request_store = None
customer_setup_activation_service = None
customer_setup_handoff_service = None
customer_setup_handoff_authorizer = None
customer_deployment_enrollment_service = None
customer_deployment_bootstrap_service = None


def _compose_customer_setup_runtime(
    app: FastAPI,
) -> None:
    global _customer_setup_runtime_composed
    global customer_setup_activation_store
    global customer_setup_handoff_store
    global customer_deployment_bootstrap_store
    global customer_deployment_package_build_request_store
    global customer_setup_activation_service
    global customer_setup_handoff_service
    global customer_setup_handoff_authorizer
    global customer_deployment_enrollment_service
    global customer_deployment_bootstrap_service

    if _customer_setup_runtime_composed:
        return

    activation_store = (
        CustomerSetupActivationStore(
            CUSTOMER_SETUP_ACTIVATION_STORAGE_PATH
        )
    )

    handoff_store = (
        CustomerSetupHandoffStore(
            CUSTOMER_SETUP_HANDOFF_STORAGE_PATH
        )
    )

    bootstrap_store = (
        CustomerDeploymentBootstrapStore(
            CUSTOMER_DEPLOYMENT_BOOTSTRAP_STORAGE_PATH
        )
    )

    build_request_store = (
        CustomerDeploymentPackageBuildRequestStore(
            CUSTOMER_DEPLOYMENT_PACKAGE_BUILD_REQUEST_STORAGE_ROOT
        )
    )

    required_owners = (
        (
            "Customer setup activation store",
            activation_store,
        ),
        (
            "Customer setup handoff store",
            handoff_store,
        ),
        (
            "Customer deployment bootstrap store",
            bootstrap_store,
        ),
        (
            "Customer deployment package build request store",
            build_request_store,
        ),
    )

    for owner_name, owner in required_owners:
        if not owner.is_ready():
            raise RuntimeError(
                f"{owner_name} is not initialized."
            )

    activation_service = (
        CustomerSetupActivationService(
            activation_store=(
                activation_store
            ),
            customer_identity_registry=(
                customer_identity_registry
            ),
            deployment_registry=(
                customer_deployment_registry
            ),
        )
    )

    handoff_service = (
        CustomerSetupHandoffService(
            handoff_store=(
                handoff_store
            ),
            setup_activation_store=(
                activation_store
            ),
        )
    )

    handoff_authorizer = (
        CustomerSetupHandoffAuthorizer(
            handoff_service=(
                handoff_service
            )
        )
    )

    enrollment_service = (
        CustomerDeploymentEnrollmentService(
            deployment_registry=(
                customer_deployment_registry
            ),
            secret_store=(
                customer_deployment_secret_store
            ),
            account_binding_store=(
                trusted_agent_account_binding_store
            ),
            runtime_projection=(
                customer_deployment_runtime_projection
            ),
        )
    )

    bootstrap_service = (
        CustomerDeploymentBootstrapService(
            bootstrap_store=(
                bootstrap_store
            ),
            deployment_registry=(
                customer_deployment_registry
            ),
            secret_store=(
                customer_deployment_secret_store
            ),
            account_binding_store=(
                trusted_agent_account_binding_store
            ),
            enrollment_service=(
                enrollment_service
            ),
        )
    )

    provisioning_router = (
        create_customer_setup_provisioning_router(
            authorize_setup_handoff=(
                handoff_authorizer.authorize
            ),
            bootstrap_service=(
                bootstrap_service
            ),
            build_request_store=(
                build_request_store
            ),
            package_publication=(
                customer_deployment_package_publication
            ),
            entitlement_registry=(
                customer_deployment_entitlement_registry
            ),
            setup_activation_service=(
                activation_service
            ),
        )
    )

    package_router = (
        create_customer_setup_package_router(
            authorize_setup_handoff=(
                handoff_authorizer.authorize
            ),
            authorize_deployment=(
                customer_deployment_authorizer.authorize
            ),
            authorize_entitlement=(
                customer_deployment_entitlement_authorizer
                .authorize
            ),
            package_publication=(
                customer_deployment_package_publication
            ),
        )
    )

    app.include_router(
        provisioning_router
    )

    app.include_router(
        package_router
    )

    customer_setup_activation_store = (
        activation_store
    )
    customer_setup_handoff_store = (
        handoff_store
    )
    customer_deployment_bootstrap_store = (
        bootstrap_store
    )
    customer_deployment_package_build_request_store = (
        build_request_store
    )
    customer_setup_activation_service = (
        activation_service
    )
    customer_setup_handoff_service = (
        handoff_service
    )
    customer_setup_handoff_authorizer = (
        handoff_authorizer
    )
    customer_deployment_enrollment_service = (
        enrollment_service
    )
    customer_deployment_bootstrap_service = (
        bootstrap_service
    )

    _customer_setup_runtime_composed = True


def refresh_customer_deployment_runtime_projection(
) -> int:
    return (
        customer_deployment_runtime_projection
        .project()
    )


refresh_customer_deployment_runtime_projection()

todoba_runtime: TODOBARuntime = create_runtime(
    RuntimeMode(
        TODOBA_RUNTIME_MODE
    )
)


def _process_recovered_execution_mission_evidence(
) -> int:
    evidence_processors = (
        (
            execution_mission_acknowledgement_store,
            execution_mission_acknowledgement_processor,
        ),
        (
            execution_mission_execution_started_store,
            execution_mission_execution_started_processor,
        ),
        (
            broker_execution_evidence_store,
            broker_execution_evidence_processor,
        ),
        (
            execution_mission_completed_store,
            execution_mission_completed_processor,
        ),
        (
            execution_mission_failed_store,
            execution_mission_failed_processor,
        ),
    )

    processed = 0

    while True:
        processed_in_cycle = False

        for store, processor in evidence_processors:
            if store.size() == 0:
                continue

            processor.process_next()

            processed += 1
            processed_in_cycle = True

        if not processed_in_cycle:
            return processed


def _require_trusted_agent_account_bindings(
) -> tuple[
    str,
    ...,
]:
    bound_accounts: list[str] = []

    for target in execution_target_registry.all():
        bound_accounts.append(
            trusted_agent_account_binding_guard.require_binding(
                agent_id=target.agent_id,
                account_fingerprint=(
                    target.account_fingerprint
                ),
            )
        )

    return tuple(
        bound_accounts
    )


def _require_trusted_agent_account_binding(
) -> str:
    bound_accounts = (
        _require_trusted_agent_account_bindings()
    )

    if len(
        bound_accounts
    ) != 1:
        raise RuntimeError(
            "Single Trusted Agent account binding "
            "requires exactly one deployment."
        )

    return bound_accounts[0]


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    refresh_customer_deployment_runtime_projection()

    _require_trusted_agent_account_bindings()

    _compose_customer_setup_runtime(
        app
    )

    execution_mission_record_recovery.restore()

    execution_mission_delivery_lease_recovery.restore()

    execution_mission_evidence_persistence.restore(
        acknowledgement_store=(
            execution_mission_acknowledgement_store
        ),
        execution_started_store=(
            execution_mission_execution_started_store
        ),
        completed_store=(
            execution_mission_completed_store
        ),
        failed_store=(
            execution_mission_failed_store
        ),
        broker_evidence_store=(
            broker_execution_evidence_store
        ),
        mission_registry=(
            execution_mission_registry
        ),
        idempotency_registry=(
            execution_mission_evidence_idempotency_registry
        ),
    )

    _process_recovered_execution_mission_evidence()

    execution_mission_recovery.restore()

    control_mission_record_recovery.restore()

    control_mission_delivery_lease_recovery.restore()

    control_mission_recovery.restore()

    await todoba_runtime.start()

    yield

    await todoba_runtime.stop()


app = FastAPI(
    lifespan=lifespan,
)


trusted_agent_authenticator = (
    TrustedAgentAuthenticator(
        credential_registry=(
            trusted_agent_credential_registry
        ),
    )
)
executor_authenticator = (
    ExecutorAuthenticator(
        executor_id=TODOBA_EXECUTOR_ID,
        executor_secret=TODOBA_EXECUTOR_SECRET,
    )
)


control_security_sequence_allocator = (
    PersistentSecuritySequenceAllocator(
        CONTROL_SECURITY_SEQUENCE_STORAGE_PATH
    )
)

control_security_sequence_binding_store = (
    PersistentSecuritySequenceBindingStore(
        CONTROL_SECURITY_SEQUENCE_BINDING_STORAGE_PATH
    )
)

control_security_sequence_assignment_service = (
    SecuritySequenceAssignmentService(
        allocator=control_security_sequence_allocator,
        binding_store=(
            control_security_sequence_binding_store
        ),
    )
)


control_mission_repository = (
    ControlMissionRepository()
)

control_mission_signer = (
    ControlMissionSigner(
        signing_key_registry=(
            control_signing_key_registry
        )
    )
)

control_mission_signer_v2 = (
    ControlMissionSignerV2(
        signing_key_registry=(
            control_signing_key_registry
        )
    )
)

control_mission_persistence = (
    ControlMissionPersistence(
        CONTROL_MISSION_STORAGE_PATH
    )
)

control_mission_store = (
    ControlMissionStore()
)

control_mission_delivery_bridge = (
    ControlMissionDeliveryBridge(
        control_mission_store
    )
)

control_mission_delivery_lease_registry = (
    ControlMissionDeliveryLeaseRegistry()
)

control_mission_delivery_lease_persistence = (
    ControlMissionDeliveryLeasePersistence(
        CONTROL_MISSION_DELIVERY_LEASE_STORAGE_PATH
    )
)

control_mission_delivery_lease_recovery = (
    ControlMissionDeliveryLeaseRecovery(
        persistence=(
            control_mission_delivery_lease_persistence
        ),
        registry=(
            control_mission_delivery_lease_registry
        ),
    )
)

control_mission_delivery_expiration_policy = (
    ControlMissionDeliveryExpirationPolicy()
)

control_mission_delivery_lease_service = (
    ControlMissionDeliveryLeaseService(
        registry=(
            control_mission_delivery_lease_registry
        ),
        lease_seconds=30.0,
        persistence=(
            control_mission_delivery_lease_persistence
        ),
    )
)

control_mission_registry = (
    ControlMissionRegistry()
)

control_mission_record_persistence = (
    ControlMissionRecordPersistence(
        CONTROL_MISSION_RECORD_STORAGE_PATH
    )
)

control_mission_lifecycle_service = (
    ControlMissionLifecycleService(
        control_mission_registry,
        control_mission_record_persistence,
        repository=control_mission_repository,
        mission_persistence=control_mission_persistence,
        lease_registry=(
            control_mission_delivery_lease_registry
        ),
        lease_persistence=(
            control_mission_delivery_lease_persistence
        ),
    )
)

control_mission_service = (
    ControlMissionService(
        control_mission_repository,
        control_mission_persistence,
        control_mission_delivery_bridge,
        control_mission_registry,
        control_mission_lifecycle_service,
        security_sequence_assignment_service=(
            control_security_sequence_assignment_service
        ),
    )
)

control_mission_recovery = (
    ControlMissionRecovery(
        repository=control_mission_repository,
        persistence=control_mission_persistence,
        delivery_bridge=control_mission_delivery_bridge,
        registry=control_mission_registry,
        lifecycle_service=control_mission_lifecycle_service,
        lease_registry=(
            control_mission_delivery_lease_registry
        ),
    )
)

control_mission_record_recovery = (
    ControlMissionRecordRecovery(
        persistence=control_mission_record_persistence,
        registry=control_mission_registry,
    )
)

control_mission_delivery_redelivery_processor = (
    ControlMissionDeliveryRedeliveryProcessor(
        repository=control_mission_repository,
        delivery_bridge=control_mission_delivery_bridge,
        lease_registry=(
            control_mission_delivery_lease_registry
        ),
        lease_persistence=(
            control_mission_delivery_lease_persistence
        ),
        lifecycle_service=(
            control_mission_lifecycle_service
        ),
        max_delivery_attempts=3,
    )
)

control_mission_lifecycle_scheduler = (
    ControlMissionLifecycleScheduler(
        processor=(
            control_mission_delivery_redelivery_processor
        ),
        interval_seconds=5.0,
    )
)


execution_security_sequence_allocator = (
    PersistentSecuritySequenceAllocator(
        EXECUTION_SECURITY_SEQUENCE_STORAGE_PATH
    )
)

execution_security_sequence_binding_store = (
    PersistentSecuritySequenceBindingStore(
        EXECUTION_SECURITY_SEQUENCE_BINDING_STORAGE_PATH
    )
)

execution_security_sequence_assignment_service = (
    SecuritySequenceAssignmentService(
        allocator=execution_security_sequence_allocator,
        binding_store=(
            execution_security_sequence_binding_store
        ),
    )
)


execution_mission_repository = (
    ExecutionMissionRepository()
)

execution_mission_signer = (
    ExecutionMissionSigner(
        signing_key_registry=(
            execution_signing_key_registry
        )
    )
)

execution_mission_signer_v2 = (
    ExecutionMissionSignerV2(
        signing_key_registry=(
            execution_signing_key_registry
        )
    )
)

execution_mission_persistence = (
    ExecutionMissionPersistence(
        MISSION_STORAGE_PATH
    )
)

execution_mission_store = (
    ExecutionMissionStore()
)

broker_state_store = (
    BrokerStateStore()
)

execution_mission_release_guard = (
    ExecutionMissionReleaseGuard(
        broker_state_store=broker_state_store,
        account_binding_guard=(
            trusted_agent_account_binding_guard
        ),
        max_age_seconds=30.0,
    )
)

execution_mission_delivery_bridge = (
    ExecutionMissionDeliveryBridge(
        execution_mission_store
    )
)

execution_mission_delivery_lease_registry = (
    ExecutionMissionDeliveryLeaseRegistry()
)

execution_mission_delivery_lease_persistence = (
    ExecutionMissionDeliveryLeasePersistence(
        MISSION_DELIVERY_LEASE_STORAGE_PATH
    )
)

execution_mission_delivery_lease_recovery = (
    ExecutionMissionDeliveryLeaseRecovery(
        persistence=(
            execution_mission_delivery_lease_persistence
        ),
        registry=(
            execution_mission_delivery_lease_registry
        ),
    )
)

execution_mission_delivery_expiration_policy = (
    ExecutionMissionDeliveryExpirationPolicy()
)

execution_mission_delivery_lease_service = (
    ExecutionMissionDeliveryLeaseService(
        registry=(
            execution_mission_delivery_lease_registry
        ),
        lease_seconds=30.0,
        persistence=(
            execution_mission_delivery_lease_persistence
        ),
    )
)

execution_mission_registry = (
    ExecutionMissionRegistry()
)

execution_mission_record_persistence = (
    ExecutionMissionRecordPersistence(
        MISSION_RECORD_STORAGE_PATH
    )
)

execution_mission_service = (
    ExecutionMissionService(
        execution_mission_repository,
        execution_mission_persistence,
        execution_mission_delivery_bridge,
        execution_mission_registry,
        execution_mission_record_persistence,
        security_sequence_assignment_service=(
            execution_security_sequence_assignment_service
        ),
    )
)

execution_mission_recovery = (
    ExecutionMissionRecovery(
        repository=execution_mission_repository,
        persistence=execution_mission_persistence,
        delivery_bridge=execution_mission_delivery_bridge,
        registry=execution_mission_registry,
    )
)

execution_mission_record_recovery = (
    ExecutionMissionRecordRecovery(
        persistence=execution_mission_record_persistence,
        registry=execution_mission_registry,
    )
)

execution_mission_record_retention_policy = (
    ExecutionMissionRecordRetentionPolicy(
        retention_days=30
    )
)

execution_mission_record_cleanup = (
    ExecutionMissionRecordCleanup(
        execution_mission_registry,
        execution_mission_record_persistence,
    )
)

execution_mission_record_retention_scheduler = (
    ExecutionMissionRecordRetentionScheduler(
        policy=execution_mission_record_retention_policy,
        cleanup=execution_mission_record_cleanup,
        interval_seconds=3600.0,
    )
)


execution_mission_acknowledgement_store = (
    ExecutionMissionAcknowledgementStore()
)

execution_mission_execution_started_store = (
    ExecutionMissionExecutionStartedStore()
)

execution_mission_completed_store = (
    ExecutionMissionCompletedStore()
)

execution_mission_failed_store = (
    ExecutionMissionFailedStore()
)

broker_execution_evidence_store = (
    BrokerExecutionEvidenceStore()
)

execution_mission_evidence_persistence = (
    ExecutionMissionEvidencePersistence(
        MISSION_EVIDENCE_STORAGE_PATH
    )
)

execution_mission_evidence_idempotency_registry = (
    ExecutionMissionEvidenceIdempotencyRegistry()
)

execution_mission_evidence_intake = (
    ExecutionMissionEvidenceIntake(
        persistence=execution_mission_evidence_persistence,
        acknowledgement_store=(
            execution_mission_acknowledgement_store
        ),
        execution_started_store=(
            execution_mission_execution_started_store
        ),
        completed_store=(
            execution_mission_completed_store
        ),
        failed_store=(
            execution_mission_failed_store
        ),
        broker_evidence_store=(
            broker_execution_evidence_store
        ),
        mission_registry=(
            execution_mission_registry
        ),
        idempotency_registry=(
            execution_mission_evidence_idempotency_registry
        ),
    )
)


execution_mission_lifecycle_service = (
    ExecutionMissionLifecycleService(
        execution_mission_registry,
        execution_mission_record_persistence,
        repository=execution_mission_repository,
        mission_persistence=execution_mission_persistence,
        lease_registry=(
            execution_mission_delivery_lease_registry
        ),
        lease_persistence=(
            execution_mission_delivery_lease_persistence
        ),
    )
)

execution_mission_acknowledgement_processor = (
    ExecutionMissionAcknowledgementProcessor(
        store=execution_mission_acknowledgement_store,
        lifecycle_service=execution_mission_lifecycle_service,
        persistence=execution_mission_evidence_persistence,
        lease_registry=(
            execution_mission_delivery_lease_registry
        ),
        lease_persistence=(
            execution_mission_delivery_lease_persistence
        ),
    )
)

execution_mission_execution_started_processor = (
    ExecutionMissionExecutionStartedProcessor(
        store=execution_mission_execution_started_store,
        lifecycle_service=execution_mission_lifecycle_service,
        persistence=execution_mission_evidence_persistence,
    )
)

execution_mission_completed_processor = (
    ExecutionMissionCompletedProcessor(
        store=execution_mission_completed_store,
        lifecycle_service=execution_mission_lifecycle_service,
        persistence=execution_mission_evidence_persistence,
    )
)

execution_mission_failed_processor = (
    ExecutionMissionFailedProcessor(
        store=execution_mission_failed_store,
        lifecycle_service=execution_mission_lifecycle_service,
        persistence=execution_mission_evidence_persistence,
    )
)

broker_execution_evidence_processor = (
    BrokerExecutionEvidenceProcessor(
        store=broker_execution_evidence_store,
        lifecycle_service=execution_mission_lifecycle_service,
        persistence=execution_mission_evidence_persistence,
    )
)

execution_mission_delivery_redelivery_processor = (
    ExecutionMissionDeliveryRedeliveryProcessor(
        repository=execution_mission_repository,
        delivery_bridge=execution_mission_delivery_bridge,
        lease_registry=(
            execution_mission_delivery_lease_registry
        ),
        lease_persistence=(
            execution_mission_delivery_lease_persistence
        ),
        lifecycle_service=(
            execution_mission_lifecycle_service
        ),
        max_delivery_attempts=3,
    )
)

execution_mission_lifecycle_scheduler = (
    ExecutionMissionLifecycleScheduler(
        processors=[
            execution_mission_acknowledgement_processor,
            execution_mission_execution_started_processor,
            execution_mission_completed_processor,
            execution_mission_failed_processor,
            broker_execution_evidence_processor,
            execution_mission_delivery_redelivery_processor,
        ],
        interval_seconds=5.0,
    )
)

todoba_runtime.register(
    start=execution_mission_lifecycle_scheduler.start,
    stop=execution_mission_lifecycle_scheduler.stop,
)

todoba_runtime.register(
    start=execution_mission_record_retention_scheduler.start,
    stop=execution_mission_record_retention_scheduler.stop,
)

todoba_runtime.register(
    start=control_mission_lifecycle_scheduler.start,
    stop=control_mission_lifecycle_scheduler.stop,
)

app.include_router(
    create_broker_state_router(
        store=broker_state_store,
        authenticator=trusted_agent_authenticator,
        executor_authenticator=(
            executor_authenticator
        ),
        account_binding_guard=(
            trusted_agent_account_binding_guard
        ),
    )
)


app.include_router(
    create_execution_mission_router(
        execution_mission_store,
        trusted_agent_authenticator,
        execution_mission_delivery_lease_service,
        execution_mission_lifecycle_service,
        execution_mission_delivery_expiration_policy,
        execution_mission_signer,
        release_guard=(
            execution_mission_release_guard
        ),
        signer_v2=execution_mission_signer_v2,
    )
)

app.include_router(
    create_execution_mission_injection_router(
        execution_mission_service,
        executor_authenticator,
    )
)

app.include_router(
    create_execution_mission_status_router(
        execution_mission_registry
    )
)

app.include_router(
    create_execution_mission_acknowledgement_router(
        execution_mission_evidence_intake,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_execution_mission_execution_started_router(
        execution_mission_evidence_intake,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_execution_mission_completed_router(
        execution_mission_evidence_intake,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_broker_execution_evidence_router(
        execution_mission_evidence_intake,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_execution_mission_failed_router(
        execution_mission_evidence_intake,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_control_mission_router(
        control_mission_store,
        trusted_agent_authenticator,
        control_mission_delivery_lease_service,
        control_mission_lifecycle_service,
        control_mission_delivery_expiration_policy,
        control_mission_signer,
        signer_v2=control_mission_signer_v2,
    )
)

app.include_router(
    create_control_mission_injection_router(
        control_mission_service,
        executor_authenticator,
    )
)

app.include_router(
    create_control_mission_lifecycle_router(
        control_mission_lifecycle_service,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_customer_deployment_package_router(
        customer_authentication_dependency=(
            customer_authentication_dependency
        ),
        deployment_authorizer=(
            customer_deployment_authorizer
        ),
        entitlement_authorizer=(
            customer_deployment_entitlement_authorizer
        ),
        package_publication=(
            customer_deployment_package_publication
        ),
    )
)


class ExperienceRequest(BaseModel):
    source: str
    content: str


@app.get("/")
def home():
    return {
        "company": "TODOBA",
        "version": "1.0.0",
        "status": "running",
        "message": "Welcome Founder!",
    }


@app.get(
    "/brain",
    response_class=HTMLResponse,
)
def brain():
    file = Path(
        "backend/brain/identity.md"
    )

    if file.exists():
        content = file.read_text(
            encoding="utf-8"
        )
    else:
        content = "Brain not found."

    return f"""
    <html>
        <head>
            <title>TODOBA Brain</title>
        </head>
        <body style="font-family:Arial;padding:40px;">
            <h1>TODOBA Brain</h1>
            <pre>{content}</pre>
        </body>
    </html>
    """


@app.get("/memory")
def memory():
    objects = memory_engine.list()

    return {
        "memory_count": len(objects),
        "objects": [
            str(obj)
            for obj in objects
        ],
    }


@app.post("/brain/experience")
def receive_experience(
    request: ExperienceRequest,
):
    experience = Experience(
        source=request.source,
        content=request.content,
    )

    task = brain_engine.process(
        experience
    )

    return {
        "status": "received",
        "task_created": task is not None,
        "task_id": (
            task.task_id
            if task is not None
            else None
        ),
    }
