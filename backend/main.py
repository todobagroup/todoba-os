from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.brain_engine import brain_engine
from backend.brain.memory import memory_engine
from backend.brain.models.experience import Experience


app = FastAPI()


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


@app.get("/brain", response_class=HTMLResponse)
def brain():
    file = Path("backend/brain/identity.md")

    if file.exists():
        content = file.read_text(encoding="utf-8")
    else:
        content = "Brain not found."

    return f"""
    <html>
        <head>
            <title>TODOBA Brain</title>
        </head>
        <body style="font-family:Arial;padding:40px;">
            <h1>🧠 TODOBA Brain</h1>
            <pre>{content}</pre>
        </body>
    </html>
    """


@app.get("/memory")
def memory():
    objects = memory_engine.list()

    return {
        "memory_count": len(objects),
        "objects": [str(obj) for obj in objects],
    }


@app.post("/brain/experience")
def receive_experience(request: ExperienceRequest):
    experience = Experience(
        source=request.source,
        content=request.content,
    )

    task = brain_engine.process(experience)

    return {
        "status": "received",
        "task_created": task is not None,
        "task_id": task.task_id if task is not None else None,
    }