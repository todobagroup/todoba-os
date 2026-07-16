"""
TODOBA Runtime Health Report

Represents the operational health of the
Trading Department and its runtime services.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeHealthReport:
    """
    Immutable runtime health snapshot.
    """

    department_ready: bool
    runtime_ready: bool
    scheduler_running: bool
    persistence_ready: bool
    repository_ready: bool
    memory_ready: bool
    mt5_ready: bool

    open_trade_count: int
    restored_trade_count: int

    @property
    def healthy(self) -> bool:
        """
        Return True when every required service is ready.
        """

        return all(
            (
                self.department_ready,
                self.runtime_ready,
                self.scheduler_running,
                self.persistence_ready,
                self.repository_ready,
                self.memory_ready,
                self.mt5_ready,
            )
        )