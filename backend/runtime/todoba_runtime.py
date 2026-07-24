"""
TODOBA Runtime

Owns the lifecycle of the TODOBA system.

Responsibilities:
- Start services
- Stop services
- Manage runtime lifecycle

Runtime does NOT own:
- Telegram logic
- MT5 execution
- Trading decisions
"""

from __future__ import annotations

from typing import Awaitable, Callable


AsyncService = Callable[[], Awaitable[None]]


class TODOBARuntime:
    """
    Owns the lifecycle of TODOBA.
    """

    def __init__(self) -> None:
        self._start_services: list[AsyncService] = []
        self._stop_services: list[AsyncService] = []

    def register(
        self,
        *,
        start: AsyncService,
        stop: AsyncService,
    ) -> None:
        self._start_services.append(start)
        self._stop_services.insert(0, stop)

    async def start(self) -> None:
        print("[Runtime] Starting...")

        for service in self._start_services:
            await service()

    async def stop(self) -> None:
        for service in self._stop_services:
            await service()

        print("[Runtime] Stopped.")