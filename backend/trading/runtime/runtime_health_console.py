"""
TODOBA Runtime Health Console

Console presentation for RuntimeHealthReport.
"""

from backend.trading.runtime.runtime_health_report import (
    RuntimeHealthReport,
)


def print_runtime_health(
    report: RuntimeHealthReport,
) -> None:
    """
    Print a human-readable runtime health report.
    """

    print()

    print("=" * 42)
    print("TODOBA SYSTEM HEALTH")
    print("=" * 42)

    print(
        f"Department .......... "
        f"{'READY' if report.department_ready else 'NOT READY'}"
    )

    print(
        f"Runtime ............. "
        f"{'READY' if report.runtime_ready else 'NOT READY'}"
    )

    print(
        f"Scheduler ........... "
        f"{'RUNNING' if report.scheduler_running else 'STOPPED'}"
    )

    print(
        f"Persistence ......... "
        f"{'READY' if report.persistence_ready else 'NOT READY'}"
    )

    print(
        f"Repository .......... "
        f"{'READY' if report.repository_ready else 'NOT READY'}"
    )

    print(
        f"Memory .............. "
        f"{'READY' if report.memory_ready else 'NOT READY'}"
    )

    print(
        f"MT5 ................. "
        f"{'READY' if report.mt5_ready else 'NOT READY'}"
    )

    print(
        f"Open Trades ......... "
        f"{report.open_trade_count}"
    )

    print(
        f"Restored Trades ..... "
        f"{report.restored_trade_count}"
    )

    print(
        f"Overall ............. "
        f"{'HEALTHY' if report.healthy else 'UNHEALTHY'}"
    )

    print("=" * 42)
    print()