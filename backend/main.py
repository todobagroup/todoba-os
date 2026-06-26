from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path

app = FastAPI()


@app.get("/")
def home():
    return {
        "company": "TODOBA",
        "version": "1.0.0",
        "status": "running",
        "message": "Welcome Founder!"
    }


@app.get("/brain", response_class=HTMLResponse)
def brain():

    file = Path("brain/identity.md")

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