"""
TODOBA API Entry Point

Starts the TODOBA FastAPI application.

This runtime owns HTTP serving only.
Executor and Trading lifecycles belong to separate
runtime capabilities.
"""

import uvicorn

from backend.config import (
    TODOBA_API_HOST,
    TODOBA_API_PORT,
)


def main() -> None:
    uvicorn.run(
        "backend.main:app",
        host=TODOBA_API_HOST,
        port=TODOBA_API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()