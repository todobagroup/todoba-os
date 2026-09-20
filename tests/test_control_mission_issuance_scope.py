from pathlib import Path


OWNER = Path(
    "backend/trading/control/"
    "control_mission_issuance_scope.py"
)

BOOTSTRAP = Path(
    "backend/runtime/runtime_bootstrap.py"
)


def test_control_mission_issuance_scope_owner_exists():
    assert OWNER.exists()


def test_scope_owns_authoritative_symbols_and_internal_sender():
    source = OWNER.read_text(
        encoding="utf-8-sig"
    )

    for required in (
        "PRODUCTION_CONTROL_ALLOWED_SYMBOLS",
        "INTERNAL_COMMERCIAL_CONTROL_SENDER_ID",
        "TODOBA_MAGIC_NUMBER",
    ):
        assert required in source


def test_scope_reuses_execution_magic_number_authority():
    source = OWNER.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "from backend.trading.execution.execution_planner import"
        in source
    )
    assert "TODOBA_MAGIC_NUMBER" in source

    assert "TODOBA_MAGIC_NUMBER =" not in source


def test_runtime_bootstrap_consumes_shared_symbol_scope():
    source = BOOTSTRAP.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "PRODUCTION_CONTROL_ALLOWED_SYMBOLS"
        in source
    )

    assert (
        'allowed_symbols=("XAUUSD",)'
        not in source
    )


def test_internal_sender_identity_is_named_not_inline_in_containment():
    source = OWNER.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "INTERNAL_COMMERCIAL_CONTROL_SENDER_ID"
        in source
    )

    assert "requested_by_sender_id" not in source
