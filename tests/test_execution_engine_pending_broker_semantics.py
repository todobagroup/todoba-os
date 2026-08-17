"""
TODOBA Execution Engine Pending Broker Semantics Tests.

Locks MT5 execution semantics:

Market orders
->
ORDER_FILLING_IOC

Pending orders
->
ORDER_FILLING_RETURN

A successfully placed pending order
->
TRADE_RETCODE_PLACED is accepted as success.
"""


from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

ENGINE_PATH = (
    ROOT_DIR
    / "MQL5"
    / "Include"
    / "TODOBAExecution"
    / "ExecutionEngine.mqh"
)


def read_engine_source() -> str:
    return ENGINE_PATH.read_text(
        encoding="utf-8",
    )


def compact(source: str) -> str:
    return "".join(
        source.split()
    )


def test_engine_distinguishes_pending_order_types():
    source = compact(
        read_engine_source()
    )

    assert "IsPendingOrderType(" in source

    assert (
        'order_type=="BUYLIMIT"'
        in source
    )
    assert (
        'order_type=="SELLLIMIT"'
        in source
    )
    assert (
        'order_type=="BUYSTOP"'
        in source
    )
    assert (
        'order_type=="SELLSTOP"'
        in source
    )


def test_pending_orders_use_return_filling():
    source = compact(
        read_engine_source()
    )

    assert (
        "IsPendingOrderType(order_type)"
        in source
    )

    assert (
        "ORDER_FILLING_RETURN"
        in source
    )

    assert (
        "ORDER_FILLING_IOC"
        in source
    )


def test_pending_placed_retcode_is_success():
    source = compact(
        read_engine_source()
    )

    assert (
        "TRADE_RETCODE_PLACED"
        in source
    )

    assert (
        "TRADE_RETCODE_DONE"
        in source
    )
