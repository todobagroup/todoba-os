import asyncio

from backend import main


def test_main_converges_evidence_before_mission_delivery(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def require_account_bindings() -> tuple[
        str,
        ...,
    ]:
        calls.append(
            "account_bindings"
        )

        return (
            "test-account",
        )

    def compose_customer_setup_runtime(
        app,
    ) -> None:
        assert app is main.app

        calls.append(
            "customer_setup"
        )

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
            "mission_registry": (
                main.execution_mission_registry
            ),
            "idempotency_registry": (
                main.execution_mission_evidence_idempotency_registry
            ),
        }

        return 0

    def process_recovered_evidence() -> int:
        calls.append(
            "evidence_processing"
        )
        return 0

    def restore_missions() -> int:
        calls.append(
            "missions"
        )
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
        main,
        "_require_trusted_agent_account_bindings",
        require_account_bindings,
    )

    monkeypatch.setattr(
        main,
        "_compose_customer_setup_runtime",
        compose_customer_setup_runtime,
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
        main,
        "_process_recovered_execution_mission_evidence",
        process_recovered_evidence,
    )

    monkeypatch.setattr(
        main.execution_mission_recovery,
        "restore",
        restore_missions,
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
                "account_bindings",
                "customer_setup",
                "records",
                "delivery_leases",
                "evidence",
                "evidence_processing",
                "missions",
                "runtime_start",
            ]

    asyncio.run(
        run_lifespan()
    )

    assert calls == [
        "account_bindings",
        "customer_setup",
        "records",
        "delivery_leases",
        "evidence",
        "evidence_processing",
        "missions",
        "runtime_start",
        "runtime_stop",
    ]