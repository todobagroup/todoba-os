import asyncio

from backend import main


def test_main_restores_evidence_before_runtime_start(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def restore_missions() -> int:
        calls.append(
            "missions"
        )
        return 0

    def restore_records() -> int:
        calls.append(
            "records"
        )
        return 0

    def restore_delivery_leases() -> int:
        calls.append(
            "delivery_leases"
        )
        return 0

    def restore_evidence(
        **stores,
    ) -> int:
        calls.append(
            "evidence"
        )

        assert stores == {
            "acknowledgement_store": (
                main.execution_mission_acknowledgement_store
            ),
            "execution_started_store": (
                main.execution_mission_execution_started_store
            ),
            "completed_store": (
                main.execution_mission_completed_store
            ),
            "failed_store": (
                main.execution_mission_failed_store
            ),
            "broker_evidence_store": (
                main.broker_execution_evidence_store
            ),
            "idempotency_registry": (
                main.execution_mission_evidence_idempotency_registry
            ),
        }

        return 0

    async def start_runtime() -> None:
        calls.append(
            "runtime_start"
        )

    async def stop_runtime() -> None:
        calls.append(
            "runtime_stop"
        )

    monkeypatch.setattr(
        main.execution_mission_recovery,
        "restore",
        restore_missions,
    )

    monkeypatch.setattr(
        main.execution_mission_record_recovery,
        "restore",
        restore_records,
    )

    monkeypatch.setattr(
        main.execution_mission_delivery_lease_recovery,
        "restore",
        restore_delivery_leases,
    )

    monkeypatch.setattr(
        main.execution_mission_evidence_persistence,
        "restore",
        restore_evidence,
    )

    monkeypatch.setattr(
        main.todoba_runtime,
        "start",
        start_runtime,
    )

    monkeypatch.setattr(
        main.todoba_runtime,
        "stop",
        stop_runtime,
    )

    async def run_lifespan() -> None:
        async with main.lifespan(
            main.app
        ):
            assert calls == [
                "records",
                "missions",
                "delivery_leases",
                "evidence",
                "runtime_start",
            ]

    asyncio.run(
        run_lifespan()
    )

    assert calls == [
        "records",
        "missions",
        "delivery_leases",
        "evidence",
        "runtime_start",
        "runtime_stop",
    ]