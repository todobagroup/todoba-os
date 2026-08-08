from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.brain.memory import memory_engine
from backend.brain.models.experience import Experience
from backend.brain_engine import brain_engine
from backend.config import (
    TODOBA_TRUSTED_AGENT_ID,
    TODOBA_TRUSTED_AGENT_SECRET,
)
from backend.runtime.runtime_bootstrap import (
    RuntimeBootstrap,
)
from backend.runtime.todoba_runtime import (
    TODOBARuntime,
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
from backend.trading.execution.execution_mission_lifecycle_scheduler import (
    ExecutionMissionLifecycleScheduler,
)
from backend.trading.execution.execution_mission_lifecycle_service import (
    ExecutionMissionLifecycleService,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
)
from backend.trading.execution.execution_mission_record_persistence import (
    ExecutionMissionRecordPersistence,
)
from backend.trading.execution.execution_mission_record_recovery import (
    ExecutionMissionRecordRecovery,
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
from backend.trading.execution.trusted_agent_authenticator import (
    TrustedAgentAuthenticator,
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


runtime_bootstrap = RuntimeBootstrap()

todoba_runtime: TODOBARuntime = (
    runtime_bootstrap.create_runtime()
)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    execution_mission_recovery.restore()

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
    idempotency_registry=(
        execution_mission_evidence_idempotency_registry
    ),
)

    await todoba_runtime.start()

    yield

    await todoba_runtime.stop()

app = FastAPI(
    lifespan=lifespan,
)


trusted_agent_authenticator = (
    TrustedAgentAuthenticator(
        agent_id=TODOBA_TRUSTED_AGENT_ID,
        agent_secret=TODOBA_TRUSTED_AGENT_SECRET,
    )
)


execution_mission_repository = (
    ExecutionMissionRepository()
)

execution_mission_persistence = (
    ExecutionMissionPersistence(
        MISSION_STORAGE_PATH
    )
)

execution_mission_store = (
    ExecutionMissionStore()
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
    )
)

execution_mission_recovery = (
    ExecutionMissionRecovery(
        repository=execution_mission_repository,
        persistence=execution_mission_persistence,
        delivery_bridge=execution_mission_delivery_bridge,
    )
)

execution_mission_record_recovery = (
    ExecutionMissionRecordRecovery(
        persistence=execution_mission_record_persistence,
        registry=execution_mission_registry,
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
        idempotency_registry=(
            execution_mission_evidence_idempotency_registry
        ),
    )
)


execution_mission_lifecycle_service = (
    ExecutionMissionLifecycleService(
        execution_mission_registry,
        execution_mission_record_persistence,
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


app.include_router(
    create_execution_mission_router(
        execution_mission_store,
        trusted_agent_authenticator,
        execution_mission_delivery_lease_service,
    )
)

app.include_router(
    create_execution_mission_injection_router(
        execution_mission_service
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