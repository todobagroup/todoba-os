"""
TODOBA Executor Supervisor

Keeps the TODOBA Executor alive.

The Supervisor owns process recovery only.

It never performs trading,
never parses Telegram,
and never executes MT5 orders.
"""

from __future__ import annotations

import time
from typing import Callable


class ExecutorSupervisor:
    """
    Supervises one long-running executor.

    If the executor stops unexpectedly,
    Supervisor waits and starts it again.
    """

    def __init__(
        self,
        runner: Callable[[], None],
        *,
        restart_delay_seconds: float = 5.0,
    ):
        if not callable(runner):
            raise TypeError(
                "runner must be callable."
            )

        if restart_delay_seconds <= 0:
            raise ValueError(
                "restart_delay_seconds must be greater than zero."
            )

        self.runner = runner
        self.restart_delay_seconds = (
            restart_delay_seconds
        )

        self.running = False
        self.restart_count = 0

    def stop(self) -> None:
        """
        Stop supervising.
        """

        self.running = False

    def run(self) -> None:
        """
        Keep the executor alive forever.

        Ctrl+C stops the Supervisor.
        """

        self.running = True

        while self.running:

            try:

                print(
                    "[Supervisor] Starting Executor..."
                )

                self.runner()

                print(
                    "[Supervisor] Executor stopped normally."
                )

                break

            except KeyboardInterrupt:

                print(
                    "[Supervisor] Shutdown requested."
                )

                break

            except Exception as error:

                self.restart_count += 1

                print(
                    "[Supervisor] Executor crashed."
                )

                print(
                    f"[Supervisor] Reason: {error}"
                )

                print(
                    f"[Supervisor] Restart #{self.restart_count}"
                )

                time.sleep(
                    self.restart_delay_seconds
                )

        self.running = False