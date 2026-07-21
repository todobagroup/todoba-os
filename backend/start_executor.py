"""
TODOBA Executor Entry Point

Starts the TODOBA Executor under the
Executor Supervisor.
"""

from __future__ import annotations

import asyncio

from backend.integrations.telegram_listener import (
    main as telegram_listener_main,
)
from backend.runtime.executor_supervisor import (
    ExecutorSupervisor,
)


def run_executor() -> None:
    """
    Execute one complete Telegram Listener lifecycle.
    """
    asyncio.run(
        telegram_listener_main()
    )


def main() -> None:
    supervisor = ExecutorSupervisor(
        runner=run_executor,
        restart_delay_seconds=5.0,
    )

    supervisor.run()


if __name__ == "__main__":
    main()