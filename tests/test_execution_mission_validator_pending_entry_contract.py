"""
TODOBA Execution Mission Validator Pending Entry Contract Tests.

Locks the Trusted Agent fail-closed invariant:

Pending execution missions
->
must contain an explicit entry price
before broker execution is allowed.
"""


from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

VALIDATOR_PATH = (
    ROOT_DIR
    / "MQL5"
    / "Include"
    / "TODOBAExecution"
    / "ExecutionMissionValidator.mqh"
)


def read_validator_source() -> str:
    return VALIDATOR_PATH.read_text(
        encoding="utf-8",
    )


def compact(source: str) -> str:
    return "".join(
        source.split()
    )


def test_pending_order_types_require_entry():
    source = compact(
        read_validator_source()
    )

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

    assert (
        "IsPendingOrderType("
        in source
    )

    assert (
        "IsPendingOrderType("
        "mission.order_type"
        ")&&!mission.has_entry"
        in source
    )
