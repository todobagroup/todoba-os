import ast
from pathlib import Path

from backend.commercial.customer_commercial_fx_snapshot_service import (
    open_or_initialize_customer_commercial_fx_snapshot_store,
)
from backend.commercial.customer_commercial_vnd_order_pricing_projection import (
    open_or_initialize_customer_commercial_vnd_order_pricing_projection_store,
)


MAIN_PATH = Path("backend/main.py")


def _main_source() -> str:
    return MAIN_PATH.read_text(
        encoding="utf-8"
    )


def _function_source(
    function_name: str,
) -> str:
    source = _main_source()
    tree = ast.parse(source)
    lines = source.splitlines()

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ) and node.name == function_name:
            return "\n".join(
                lines[
                    node.lineno - 1:
                    node.end_lineno
                ]
            )

    raise AssertionError(
        f"{function_name} not found"
    )


def test_fx_snapshot_bootstrap_initializes_new_store(
    tmp_path: Path,
):
    path = tmp_path / "fx.json"

    store = (
        open_or_initialize_customer_commercial_fx_snapshot_store(
            path
        )
    )

    assert path.is_file()
    assert store.is_ready()


def test_fx_snapshot_bootstrap_reopens_existing_store(
    tmp_path: Path,
):
    path = tmp_path / "fx.json"

    first = (
        open_or_initialize_customer_commercial_fx_snapshot_store(
            path
        )
    )
    assert first.is_ready()

    restored = (
        open_or_initialize_customer_commercial_fx_snapshot_store(
            path
        )
    )

    assert restored.is_ready()


def test_vnd_projection_bootstrap_initializes_new_store(
    tmp_path: Path,
):
    path = tmp_path / "projection.json"

    store = (
        open_or_initialize_customer_commercial_vnd_order_pricing_projection_store(
            path
        )
    )

    assert path.is_file()
    assert store.is_ready()


def test_vnd_projection_bootstrap_reopens_existing_store(
    tmp_path: Path,
):
    path = tmp_path / "projection.json"

    first = (
        open_or_initialize_customer_commercial_vnd_order_pricing_projection_store(
            path
        )
    )
    assert first.is_ready()

    restored = (
        open_or_initialize_customer_commercial_vnd_order_pricing_projection_store(
            path
        )
    )

    assert restored.is_ready()


def test_production_composes_existing_vnd_pricing_owners():
    source = _main_source()

    required = (
        "open_or_initialize_customer_commercial_fx_snapshot_store",
        "VietcombankFXAdapter",
        "CustomerCommercialFXDailyRefreshService",
        "CustomerCommercialFXDailyRefreshScheduler",
        "CustomerCommercialFXFreshnessGate",
        "open_or_initialize_customer_commercial_vnd_order_pricing_projection_store",
        "CustomerCommercialVndOrderPricingProjectionService",
    )

    for owner in required:
        assert owner in source


def test_production_main_owns_no_durable_initialization():
    source = _main_source()

    assert ".initialize_empty()" not in source


def test_production_pricing_policy_values_are_exact():
    composer = _function_source(
        "_compose_customer_vnd_pricing_runtime"
    )

    assert "timeout_seconds=5.0" in composer
    assert "VIETCOMBANK_FX_SOURCE_ID" in composer
    assert "hours=48" in composer
    assert (
        "source_id=VIETCOMBANK_FX_SOURCE_ID"
        in composer
    )


def test_main_delegates_fx_store_bootstrap_to_store_owner():
    composer = _function_source(
        "_compose_customer_vnd_pricing_runtime"
    )

    assert (
        "open_or_initialize_customer_commercial_fx_snapshot_store("
        in composer
    )

    assert "fx_snapshot_store.load()" not in composer
    assert "fx_snapshot_store.initialize_empty()" not in composer


def test_main_delegates_projection_store_bootstrap_to_store_owner():
    composer = _function_source(
        "_compose_customer_vnd_pricing_runtime"
    )

    assert (
        "open_or_initialize_customer_commercial_vnd_order_pricing_projection_store("
        in composer
    )

    assert (
        "vnd_order_pricing_projection_store.initialize_empty()"
        not in composer
    )


def test_projection_service_receives_only_projection_and_fx_authority():
    composer = _function_source(
        "_compose_customer_vnd_pricing_runtime"
    )

    assert "projection_store=(" in composer
    assert (
        "fx_freshness_gate=fx_freshness_gate"
        in composer
    )

    forbidden = (
        "CustomerCommercialOrderService(",
        "CustomerPaymentIntentService(",
        "CustomerPaymentSettlementService(",
        "CustomerVndBankPaymentInstructionService(",
        "include_router(",
        "@app.",
    )

    for token in forbidden:
        assert token not in composer


def test_fx_scheduler_is_owned_by_application_lifespan():
    lifespan = _function_source(
        "lifespan"
    )

    compose_position = lifespan.index(
        "_compose_customer_vnd_pricing_runtime()"
    )
    start_position = lifespan.index(
        "customer_commercial_fx_daily_refresh_scheduler.start()"
    )
    payment_position = lifespan.index(
        "_compose_customer_payment_runtime("
    )

    assert (
        compose_position
        < start_position
        < payment_position
    )

    assert (
        "customer_commercial_fx_daily_refresh_scheduler.stop()"
        in lifespan
    )


def test_production_storage_paths_remain_server_side_commercial_data():
    source = _main_source()

    assert (
        'CUSTOMER_COMMERCIAL_FX_SNAPSHOT_STORAGE_PATH = (\n'
        '    TODOBA_CONTROL_PLANE_DATA_ROOT\n'
        '    / "commercial"\n'
        '    / "customer_commercial_fx_snapshots.json"\n'
        ')'
        in source
    )

    assert (
        'CUSTOMER_COMMERCIAL_VND_ORDER_PRICING_PROJECTION_STORAGE_PATH = (\n'
        '    TODOBA_CONTROL_PLANE_DATA_ROOT\n'
        '    / "commercial"\n'
        '    / "customer_commercial_vnd_order_pricing_projections.json"\n'
        ')'
        in source
    )
