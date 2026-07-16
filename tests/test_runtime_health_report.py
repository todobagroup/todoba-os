"""
TODOBA Runtime Health Report Tests
"""

from backend.trading.runtime.runtime_health_report import (
    RuntimeHealthReport,
)


def create_report():

    return RuntimeHealthReport(
        department_ready=True,
        runtime_ready=True,
        scheduler_running=True,
        persistence_ready=True,
        repository_ready=True,
        memory_ready=True,
        mt5_ready=True,
        open_trade_count=0,
        restored_trade_count=0,
    )


def test_runtime_is_healthy():

    report = create_report()

    assert report.healthy is True


def test_runtime_is_unhealthy_when_scheduler_stops():

    report = RuntimeHealthReport(
        department_ready=True,
        runtime_ready=True,
        scheduler_running=False,
        persistence_ready=True,
        repository_ready=True,
        memory_ready=True,
        mt5_ready=True,
        open_trade_count=0,
        restored_trade_count=0,
    )

    assert report.healthy is False