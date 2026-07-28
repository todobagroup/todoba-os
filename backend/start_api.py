"""
TODOBA API Entry Point

Starts the TODOBA FastAPI application.

This runtime owns HTTP serving only.
Executor and Trading lifecycles belong to separate
runtime capabilities.
"""

import uvicorn


def main() -> None:
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()