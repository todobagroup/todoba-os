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
from backend.trading.execution.broker_execution_evidence_store import (
    BrokerExecutionEvidenceStore,
)
from backend.trading.execution.execution_mission_api import (
    create_execution_mission_router,
)
from backend.trading.execution.execution_mission_completed_api import (
    create_execution_mission_completed_router,
)
from backend.trading.execution.execution_mission_completed_store import (
    ExecutionMissionCompletedStore,
)
from backend.trading.execution.execution_mission_delivery_bridge import (
    ExecutionMissionDeliveryBridge,
)
from backend.trading.execution.execution_mission_execution_started_api import (
    create_execution_mission_execution_started_router,
)
from backend.trading.execution.execution_mission_execution_started_store import (
    ExecutionMissionExecutionStartedStore,
)
from backend.trading.execution.execution_mission_failed_api import (
    create_execution_mission_failed_router,
)
from backend.trading.execution.execution_mission_failed_store import (
    ExecutionMissionFailedStore,
)
from backend.trading.execution.execution_mission_injection_api import (
    create_execution_mission_injection_router,
)
from backend.trading.execution.execution_mission_persistence import (
    ExecutionMissionPersistence,
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


runtime_bootstrap = RuntimeBootstrap()

todoba_runtime: TODOBARuntime = (
    runtime_bootstrap.create_runtime()
)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    execution_mission_recovery.restore()

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

execution_mission_registry = (
    ExecutionMissionRegistry()
)

execution_mission_service = (
    ExecutionMissionService(
        execution_mission_repository,
        execution_mission_persistence,
        execution_mission_delivery_bridge,
        execution_mission_registry,
    )
)

execution_mission_recovery = (
    ExecutionMissionRecovery(
        repository=execution_mission_repository,
        persistence=execution_mission_persistence,
        delivery_bridge=execution_mission_delivery_bridge,
    )
)

execution_mission_execution_started_store = (
    ExecutionMissionExecutionStartedStore()
)

execution_mission_completed_store = (
    ExecutionMissionCompletedStore()
)

broker_execution_evidence_store = (
    BrokerExecutionEvidenceStore()
)

execution_mission_failed_store = (
    ExecutionMissionFailedStore()
)


app.include_router(
    create_execution_mission_router(
        execution_mission_store,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_execution_mission_injection_router(
        execution_mission_service
    )
)

app.include_router(
    create_execution_mission_execution_started_router(
        execution_mission_execution_started_store,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_execution_mission_completed_router(
        execution_mission_completed_store,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_broker_execution_evidence_router(
        broker_execution_evidence_store,
        trusted_agent_authenticator,
    )
)

app.include_router(
    create_execution_mission_failed_router(
        execution_mission_failed_store,
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