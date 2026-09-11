from pathlib import Path


GUI = Path(
    "backend/commercial/"
    "customer_vps_connect_gui_shell.py"
)


def _source():
    return GUI.read_text(
        encoding="utf-8-sig",
    )


def test_customer_product_is_named_vps_setup():
    source = _source()

    assert (
        'WINDOW_TITLE = "TODOBA VPS Setup"'
        in source
    )

    assert (
        'text="TODOBA VPS Setup"'
        in source
    )


def test_runtime_ready_guidance_is_customer_owned_and_nontechnical():
    source = _source()

    assert (
        "TODOBA is ready."
        in source
    )

    assert (
        "Complete the VPS migration in MetaTrader 5."
        in source
    )

    assert (
        "TODOBA will verify automatically."
        in source
    )


def test_automatic_waiting_message_needs_no_customer_verify_action():
    source = _source()

    assert (
        "Waiting for MetaTrader VPS."
        in source
    )

    assert (
        "TODOBA will continue automatically."
        in source
    )


def test_guided_migration_ux_does_not_expose_technical_diagnostics():
    source = _source()

    for forbidden in (
        "Journal",
        "4014",
        "runtime_environment",
        "broker-state",
        "broker state",
        "WebRequest error",
        "common.ini",
        "AgentSecret",
        "MissionSigningSecret",
    ):
        assert forbidden not in source


def test_guided_migration_ux_does_not_claim_todoba_performs_metaquotes_migration():
    source = _source()

    for forbidden in (
        "TODOBA is migrating your VPS",
        "TODOBA migrated your VPS",
        "Migrating MetaTrader VPS automatically",
    ):
        assert forbidden not in source
