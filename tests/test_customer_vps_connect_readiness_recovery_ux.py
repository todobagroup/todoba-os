import ast
from pathlib import Path


GUI = Path(
    "backend/commercial/"
    "customer_vps_connect_gui_shell.py"
)


def _source():
    return GUI.read_text(
        encoding="utf-8-sig",
    )


def _string_constants():
    tree = ast.parse(
        _source()
    )

    return tuple(
        node.value
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        )
    )


SAFE_RECOVERY = (
    "TODOBA VPS is not ready yet. "
    "Keep MetaTrader 5 open and complete the VPS migration "
    "if needed, then select Verify."
)

AUTO_RETRY = (
    "TODOBA could not complete the automatic VPS check. "
    "Select Verify to try again."
)


def test_pending_recovery_gives_one_safe_customer_action():
    strings = _string_constants()

    assert SAFE_RECOVERY in strings


def test_observation_timeout_uses_same_safe_recovery_action():
    strings = _string_constants()

    assert strings.count(
        SAFE_RECOVERY
    ) >= 2


def test_automatic_check_failure_has_simple_retry_guidance():
    strings = _string_constants()

    assert AUTO_RETRY in strings


def test_recovery_ux_does_not_guess_root_cause():
    source = _source()

    for forbidden in (
        "Journal",
        "4014",
        "WebRequest",
        "allowlist",
        "Allow WebRequest",
        "runtime_environment",
        "broker-state",
        "broker state",
        "common.ini",
        "Expert Advisors tab",
        "Tools > Options",
        "AgentSecret",
        "MissionSigningSecret",
    ):
        assert forbidden not in source


def test_recovery_ux_does_not_weaken_vps_finish_gate():
    source = _source()

    assert (
        'if result.status == "vps_online":'
        in source
    )

    assert (
        'if result.status == "runtime_ready":'
        in source
    )

    assert (
        "begin_migration_observation"
        in source
    )

    assert (
        "observe_migration"
        in source
    )
