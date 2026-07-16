"""
TODOBA Runtime Health Factory

Creates immutable RuntimeHealthReport snapshots
from the current Trading Department state.
"""

from backend.trading.runtime.runtime_health_report import (
    RuntimeHealthReport,
)


class RuntimeHealthFactory:
    """
    Build runtime health reports.

    The factory has no side effects.
    It only observes the Trading Department.
    """

    def build(
        self,
        *,
        department,
        restored_trade_count: int,
        mt5_ready: bool,
    ) -> RuntimeHealthReport:

        return RuntimeHealthReport(
            department_ready=department.running,
            runtime_ready=True,
            scheduler_running=(
                department.lifecycle_scheduler.running
            ),
            persistence_ready=(
                department.persistence is not None
            ),
            repository_ready=(
                department.repository is not None
            ),
            memory_ready=(
                department.memory_bridge is not None
            ),
            mt5_ready=mt5_ready,
            open_trade_count=len(
                department.registry.list()
            ),
            restored_trade_count=(
                restored_trade_count
            ),
        )